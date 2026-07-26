"""Extended Cloud Run entrypoint - THE real one. This is what the Dockerfile's
CMD actually points at (`gunicorn extended_server:app`), not app.py (deleted,
was dead) and not server.py or optimize_campaigns.py directly.

ROUTING MODEL - READ BEFORE ADDING OR CHANGING A ROUTE:
This file does `from server import app`, then imports optimize_campaigns.py,
which ALSO defines routes on that same shared FastAPI `app` object via its own
`@app.get/@app.post` decorators (module-level code runs on import). Then this
file's own `@app...` decorators register last. For two routes with the exact
same path+method, Starlette matches in REGISTRATION ORDER and the FIRST one
registered wins - so plainly duplicating a path in a later-imported module
does NOT override the earlier one; it just adds silently-dead code that never
executes. (This bit a real feature once: an earlier version of this file
re-declared /api/create-campaign-from-product and / hoping to override
server.py's versions, and neither ever ran.)

The one correct way to actually override a route from server.py or
optimize_campaigns.py is the pattern below: call _remove_route(path, method)
to unregister the earlier one, then redeclare it here. Only /  and
/api/create-campaign-from-product currently need this (the latter to add
duplicate-campaign-launch protection ahead of server.py's plain launcher,
which the wrapper still calls internally as `base.api_create_recommended_
campaigns(...)` when it decides to proceed). Everything else this file adds
(/api/campaign-products, /api/acos-circuit-breaker, /api/campaign-state-live/
{id}, /api/harvest-discovery-winners) is on a path unique to this file, so no
override dance is needed for those.
"""
import datetime
import hmac
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import Body, Header
from fastapi.responses import HTMLResponse, JSONResponse

import server as base
from server import app
import optimize_campaigns
from optimize_campaigns import AmazonAdsClient, DEFAULT_FALLBACK_BID, generate_keywords_for_product, load_products, normalized_product, parse_report_json_bytes, verify_internal_token
from budget_dayparting import budget_protection_status, choose_budget_protected_bid
from ppc_waste_rules import (
    apply_negatives_step_with_match_types,
    classify_search_terms,
    summarize_classification,
)

logger = logging.getLogger(__name__)


DASHBOARD_PATCH_JS = r"""
<script>
(function(){
  function byId(id){ return document.getElementById(id); }
  function fmtMoney(v){ return '$' + Number(v || 0).toFixed(2); }
  function notify(msg, isErr){
    if (typeof toast === 'function') toast(msg, !!isErr);
    else alert(msg);
  }
  function token(){
    if (typeof getToken === 'function') return getToken();
    return (localStorage.getItem('nws_token') || '').trim();
  }
  function apiJson(url, body){
    var t = token();
    if (!t) throw new Error('Missing DAILY_OPTIMIZER_TOKEN');
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + t,
        'X-Daily-Optimizer-Token': t
      },
      body: JSON.stringify(body || {})
    }).then(function(res){
      return res.text().then(function(txt){
        var data = txt ? JSON.parse(txt) : {};
        if (!res.ok || data.error) throw new Error(data.message || data.detail || 'Request failed');
        return data;
      });
    });
  }

  function addHarvestButton(){
    var bar = document.querySelector('.prod-bar');
    if (!bar || byId('harvestDiscoveryBtn')) return;
    var btn = document.createElement('button');
    btn.id = 'harvestDiscoveryBtn';
    btn.className = 'btn btn-blue';
    btn.textContent = '🌾 Harvest Discovery Winners';
    btn.onclick = function(){
      var sku = prompt('Enter SKU to harvest from AUTO DISCOVERY into MANUAL EXACT:');
      if (!sku) return;
      btn.disabled = true;
      btn.textContent = 'Checking winners...';
      apiJson('/api/harvest-discovery-winners', {
        sku: sku.trim(),
        lookback_days: 14,
        max_terms: 25,
        apply_live: false
      }).then(function(preview){
        var terms = preview.terms_harvested || [];
        var msg = 'Preview for ' + sku + '\n\n' +
          'Rows analyzed: ' + (preview.rows_analyzed || 0) + '\n' +
          'Winners found: ' + (preview.winners_found || 0) + '\n' +
          'New exact terms selected: ' + (preview.terms_selected || 0) + '\n\n' +
          (terms.length ? terms.slice(0,25).join('\n') : 'No new winners to harvest yet.') +
          '\n\nApply live now?';
        if (!terms.length) {
          notify('No discovery winners ready to harvest yet.');
          return null;
        }
        if (!confirm(msg)) return null;
        return apiJson('/api/harvest-discovery-winners', {
          sku: sku.trim(),
          lookback_days: 14,
          max_terms: 25,
          apply_live: true
        });
      }).then(function(result){
        if (!result) return;
        notify('✅ Harvest complete: ' + (result.keywords_created || 0) + ' exact keywords added.');
        if (typeof loadDashboard === 'function') setTimeout(loadDashboard, 1500);
      }).catch(function(err){
        notify('❌ ' + err.message, true);
      }).finally(function(){
        btn.disabled = false;
        btn.textContent = '🌾 Harvest Discovery Winners';
      });
    };
    bar.appendChild(btn);
  }

  function improveLaunchText(){
    var launchBtn = byId('launchBtn');
    if (launchBtn) launchBtn.innerHTML = '🚀 Launch AUTO + EXACT';
    var sub = byId('lSub');
    if (sub && /Review and confirm/i.test(sub.textContent || '')) {
      sub.textContent = 'Creates AUTO DISCOVERY + MANUAL EXACT with seed negatives and duplicate protection.';
    }
  }

  window.doLaunch = function(){
    var pid = byId('lPid') && byId('lPid').value;
    if (!pid) return;
    var budget = +(byId('lBudget') && byId('lBudget').value);
    var bid = +(byId('lBid') && byId('lBid').value);
    if (!isFinite(budget) || budget < 1) return notify('❌ Daily budget must be at least $1.00', true);
    if (!isFinite(bid) || bid < 0.02) return notify('❌ Starting bid must be at least $0.02', true);

    var btn = byId('launchBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="loader"></span> Launching AUTO + EXACT...'; }
    apiJson('/api/create-campaign-from-product', {
      product_id: pid,
      daily_budget: Number(budget.toFixed(2)),
      starting_bid: Number(bid.toFixed(2)),
      discovery_budget_pct: 0.30,
      max_exact_keywords: 40
    }).then(function(data){
      if (data.duplicate_launch_prevented) {
        notify('✅ Duplicate prevented — existing AUTO DISCOVERY / MANUAL EXACT campaigns found.');
        return;
      }
      var campaigns = data.campaigns_created || [];
      var auto = campaigns.find(function(c){ return c.campaign_type === 'AUTO_DISCOVERY'; }) || {};
      var exact = campaigns.find(function(c){ return c.campaign_type === 'MANUAL_EXACT'; }) || {};
      var negatives = data.launch_negatives ? data.launch_negatives.negative_rows_created : 0;
      notify('✅ Launched AUTO + EXACT. Auto budget ' + fmtMoney(auto.daily_budget) +
        ', Exact budget ' + fmtMoney(exact.daily_budget) +
        ', Exact keywords ' + (exact.keyword_rows_created || 0) +
        ', Seed negatives ' + negatives + '.');
      if (typeof closeModal === 'function') closeModal();
      if (typeof loadDashboard === 'function') setTimeout(loadDashboard, 2500);
    }).catch(function(err){
      notify('❌ ' + err.message, true);
    }).finally(function(){
      if (btn) { btn.disabled = false; btn.innerHTML = '🚀 Launch AUTO + EXACT'; }
    });
  };

  function patch(){
    addHarvestButton();
    improveLaunchText();
    var oldOpen = window.openLaunch;
    if (typeof oldOpen === 'function' && !oldOpen.__nwsPatched) {
      window.openLaunch = function(pid){
        oldOpen(pid);
        setTimeout(improveLaunchText, 50);
      };
      window.openLaunch.__nwsPatched = true;
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', patch);
  else patch();
  setTimeout(patch, 1000);
})();
</script>
"""


def _remove_route(path: str, method: str) -> None:
    app.router.routes = [
        route for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and method.upper() in set(getattr(route, "methods", set()) or set())
        )
    ]


_remove_route("/api/create-campaign-from-product", "POST")
_remove_route("/", "GET")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard_with_extended_controls():
    try:
        html = base.DASHBOARD_PATH.read_text(encoding="utf-8")
        html = html.replace("</body>", DASHBOARD_PATCH_JS + "\n</body>")
        return HTMLResponse(
            html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as exc:
        return HTMLResponse(f"<h2>Dashboard Error</h2><p>{exc}</p>", status_code=500)


def _optional_dashboard_auth(authorization: Optional[str], x_daily_optimizer_token: Optional[str]) -> Optional[JSONResponse]:
    token = os.getenv("DAILY_OPTIMIZER_TOKEN", "")
    if not token:
        return None
    supplied = None
    if x_daily_optimizer_token:
        supplied = x_daily_optimizer_token.strip()
    elif authorization and authorization.startswith("Bearer "):
        supplied = authorization.replace("Bearer ", "", 1).strip()
    if supplied and not hmac.compare_digest(supplied, token):
        return JSONResponse({"error": True, "message": "Invalid token"}, status_code=403)
    return None


def _product_from_key(key: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    key = key.lower().strip()
    for row in load_products():
        if row.get("Product_ID", "").lower() == key or row.get("SKU", "").lower() == key:
            return normalized_product(row), row
    return None, {}


def _safe_title(product: Dict[str, Any]) -> str:
    return base._sanitize_name(str(product.get("title") or "Product"))[:70]


def _find_existing_launch_campaigns(client: AmazonAdsClient, safe_title: str) -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    prefix = f"{safe_title} | "
    for campaign in client.list_campaigns():
        name = str(campaign.get("name") or "")
        if not name.startswith(prefix):
            continue
        if "| AUTO DISCOVERY |" in name and "AUTO_DISCOVERY" not in found:
            found["AUTO_DISCOVERY"] = campaign
        if "| MANUAL EXACT |" in name and "MANUAL_EXACT" not in found:
            found["MANUAL_EXACT"] = campaign
    return found


def _list_ad_groups(client: AmazonAdsClient, campaign_id: str) -> List[Dict[str, Any]]:
    ad_groups: List[Dict[str, Any]] = []
    next_token: Optional[str] = None
    while True:
        body: Dict[str, Any] = {
            "maxResults": 100,
            "filters": {
                "campaignIdFilter": {"include": [str(campaign_id)]},
                "stateFilter": {"include": ["ENABLED"]},
            },
        }
        if next_token:
            body["nextToken"] = next_token
        data = client.post(
            "/sp/adGroups/list",
            body,
            content_type="application/vnd.spadgroup.v3+json",
            accept="application/vnd.spadgroup.v3+json",
        )
        if isinstance(data, dict):
            ad_groups.extend(
                group
                for group in data.get("adGroups", [])
                if str(group.get("campaignId") or "") == str(campaign_id)
            )
            next_token = data.get("nextToken")
        else:
            next_token = None
        if not next_token:
            return ad_groups


def _first_ad_group_id(client: AmazonAdsClient, campaign_id: str) -> Optional[str]:
    for ad_group in _list_ad_groups(client, campaign_id):
        if ad_group.get("adGroupId"):
            return str(ad_group["adGroupId"])
    return None


def _search_term_rows(client: AmazonAdsClient, lookback_days: int) -> Tuple[List[Dict[str, Any]], str, str, str]:
    start_date = (datetime.date.today() - datetime.timedelta(days=lookback_days)).isoformat()
    end_date = datetime.date.today().isoformat()
    report_id = client.request_report({
        "startDate": start_date,
        "endDate": end_date,
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "groupBy": ["searchTerm"],
            "columns": ["campaignId", "adGroupId", "searchTerm", "clicks", "cost", "sales7d", "purchases7d"],
            "reportTypeId": "spSearchTerm",
            "timeUnit": "SUMMARY",
            "format": "GZIP_JSON",
        },
    })
    report_url = client.wait_for_report(report_id)
    return parse_report_json_bytes(client.download_binary(report_url)), report_id, start_date, end_date


@app.post("/api/create-campaign-from-product")
def api_create_campaign_with_duplicate_protection(
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Launch using server.py logic, but block duplicate product launches first."""
    auth_error = _optional_dashboard_auth(authorization, x_daily_optimizer_token)
    if auth_error:
        return auth_error
    try:
        key = (payload.get("product_id") or payload.get("sku") or "").lower().strip()
        if not key:
            return JSONResponse({"error": True, "message": "product_id or sku required"}, status_code=400)
        product, _ = _product_from_key(key)
        if not product:
            return JSONResponse({"error": True, "message": "Product not found"}, status_code=404)

        client = AmazonAdsClient()
        safe_title = _safe_title(product)
        existing = _find_existing_launch_campaigns(client, safe_title)
        force_relaunch = bool(payload.get("force_relaunch", False))
        if existing and not force_relaunch:
            return JSONResponse({
                "success": True,
                "duplicate_launch_prevented": True,
                "message": "Matching launch campaigns already exist. No new campaigns were created. Use force_relaunch=true only when you intentionally want duplicates.",
                "product": product.get("title"),
                "existing_campaigns": {
                    campaign_type: {
                        "campaign_id": str(campaign.get("campaignId") or ""),
                        "name": campaign.get("name"),
                        "state": campaign.get("state"),
                    }
                    for campaign_type, campaign in existing.items()
                },
            })

        return base.api_create_recommended_campaigns(payload, authorization, x_daily_optimizer_token)
    except Exception as exc:
        return JSONResponse({"error": True, "message": str(exc)}, status_code=500)


@app.post("/api/harvest-discovery-winners")
def api_harvest_discovery_winners(
    payload: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Promote proven AUTO DISCOVERY search terms into MANUAL EXACT."""
    verify_internal_token(authorization, x_daily_optimizer_token)
    try:
        key = (payload.get("product_id") or payload.get("sku") or "").lower().strip()
        if not key:
            return JSONResponse({"error": True, "message": "product_id or sku required"}, status_code=400)
        product, _ = _product_from_key(key)
        if not product:
            return JSONResponse({"error": True, "message": "Product not found"}, status_code=404)

        lookback_days = max(1, min(60, int(payload.get("lookback_days", 14))))
        max_terms = max(1, min(100, int(payload.get("max_terms", 25))))
        apply_live = bool(payload.get("apply_live", True))
        fallback_bid = float(payload.get("winner_bid", product.get("suggested_bid") or DEFAULT_FALLBACK_BID))
        _, _, protected_bid = choose_budget_protected_bid({}, fallback_bid)
        exact_bid = round(max(0.10, protected_bid * 1.15), 2)

        client = AmazonAdsClient()
        existing = _find_existing_launch_campaigns(client, _safe_title(product))
        discovery_campaign = existing.get("AUTO_DISCOVERY")
        exact_campaign = existing.get("MANUAL_EXACT")
        if not discovery_campaign or not exact_campaign:
            return JSONResponse({
                "error": True,
                "message": "Could not find both AUTO DISCOVERY and MANUAL EXACT campaigns for this product.",
                "found_campaigns": list(existing.keys()),
            }, status_code=404)

        discovery_campaign_id = str(discovery_campaign.get("campaignId") or "")
        exact_campaign_id = str(exact_campaign.get("campaignId") or "")
        exact_ad_group_id = _first_ad_group_id(client, exact_campaign_id)
        if not exact_ad_group_id:
            return JSONResponse({"error": True, "message": "MANUAL EXACT campaign has no enabled ad group."}, status_code=404)

        rows, report_id, start_date, end_date = _search_term_rows(client, lookback_days)
        discovery_rows = [row for row in rows if str(row.get("campaignId") or "") == discovery_campaign_id]
        classified = classify_search_terms(discovery_rows)
        winners = sorted(
            classified.get("winners", []),
            key=lambda item: (float(item.get("sales") or 0), -float(item.get("acos") or 9)),
            reverse=True,
        )

        existing_exact_terms = {
            base._normalize_keyword(keyword.get("keywordText"))
            for keyword in client.list_keywords(exact_campaign_id)
            if str(keyword.get("matchType") or "").upper() == "EXACT"
        }
        selected_terms: List[str] = []
        skipped_existing: List[str] = []
        for item in winners:
            term = base._normalize_keyword(item.get("term"))
            if not term:
                continue
            if term in existing_exact_terms:
                skipped_existing.append(term)
                continue
            selected_terms.append(term)
            existing_exact_terms.add(term)
            if len(selected_terms) >= max_terms:
                break

        keyword_rows = base._exact_keyword_rows(selected_terms, exact_campaign_id, exact_ad_group_id, exact_bid)
        created = 0
        if apply_live and keyword_rows:
            client.create_keywords(keyword_rows)
            created = len(keyword_rows)

        return JSONResponse({
            "success": True,
            "apply_live": apply_live,
            "product": product.get("title"),
            "report_id": report_id,
            "date_range": {"start": start_date, "end": end_date},
            "budget_protection": budget_protection_status(),
            "discovery_campaign_id": discovery_campaign_id,
            "exact_campaign_id": exact_campaign_id,
            "exact_ad_group_id": exact_ad_group_id,
            "rows_analyzed": len(discovery_rows),
            "winners_found": len(winners),
            "terms_selected": len(selected_terms),
            "keywords_created": created,
            "applied_bid": exact_bid,
            "terms_harvested": selected_terms,
            "skipped_existing_sample": skipped_existing[:25],
            "summary": summarize_classification(classified),
        })
    except Exception as exc:
        return JSONResponse({"error": True, "message": str(exc)}, status_code=500)


@app.post("/api/harvest-all-discovery")
def api_harvest_all_discovery(
    payload: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Promote AUTO winners into paired EXACT campaigns and block AUTO waste."""
    verify_internal_token(authorization, x_daily_optimizer_token)
    try:
        lookback_days = max(1, min(60, int(payload.get("lookback_days", 14))))
        max_terms = max(1, min(50, int(payload.get("max_terms_per_product", 10))))
        apply_live = bool(payload.get("apply_live", True))
        client = AmazonAdsClient()
        rows, report_id, start_date, end_date = _search_term_rows(client, lookback_days)
        results: List[Dict[str, Any]] = []

        for raw_product in load_products():
            product = normalized_product(raw_product)
            existing = _find_existing_launch_campaigns(client, _safe_title(product))
            discovery = existing.get("AUTO_DISCOVERY")
            exact = existing.get("MANUAL_EXACT")
            if not discovery or not exact:
                continue
            discovery_campaign_id = str(discovery.get("campaignId") or "")
            exact_campaign_id = str(exact.get("campaignId") or "")
            exact_groups = _list_ad_groups(client, exact_campaign_id)
            if not exact_groups:
                continue
            exact_group = exact_groups[0]
            exact_ad_group_id = str(exact_group.get("adGroupId") or "")
            exact_bid = round(float(exact_group.get("defaultBid") or DEFAULT_FALLBACK_BID), 2)
            discovery_rows = [
                row for row in rows
                if str(row.get("campaignId") or "") == discovery_campaign_id
            ]
            classified = classify_search_terms(discovery_rows)
            existing_terms = {
                base._normalize_keyword(keyword.get("keywordText"))
                for keyword in client.list_keywords(exact_campaign_id)
                if str(keyword.get("matchType") or "").upper() == "EXACT"
            }
            selected: List[str] = []
            for item in sorted(
                classified.get("winners", []),
                key=lambda value: (
                    float(value.get("sales") or 0),
                    -float(value.get("acos") or 9),
                ),
                reverse=True,
            ):
                term = base._normalize_keyword(item.get("term"))
                if not term or term in existing_terms:
                    continue
                selected.append(term)
                existing_terms.add(term)
                if len(selected) >= max_terms:
                    break
            keyword_rows = base._exact_keyword_rows(
                selected, exact_campaign_id, exact_ad_group_id, exact_bid
            )
            negatives_applied: List[Dict[str, Any]] = []
            if apply_live:
                if keyword_rows:
                    client.create_keywords(keyword_rows)
                negatives_applied = apply_negatives_step_with_match_types(client, classified)
            results.append({
                "product_id": str(product.get("product_id") or product.get("sku") or ""),
                "discovery_campaign_id": discovery_campaign_id,
                "exact_campaign_id": exact_campaign_id,
                "search_terms_analyzed": len(discovery_rows),
                "winners_created": len(keyword_rows) if apply_live else 0,
                "winner_terms": selected,
                "negative_groups_applied": len(negatives_applied),
                "negative_terms_found": len(classified.get("negatives", [])),
            })

        return JSONResponse({
            "success": True,
            "apply_live": apply_live,
            "report_id": report_id,
            "date_range": {"start": start_date, "end": end_date},
            "products_processed": len(results),
            "keywords_created": sum(item["winners_created"] for item in results),
            "negative_terms_found": sum(item["negative_terms_found"] for item in results),
            "results": results,
        })
    except Exception as exc:
        return JSONResponse({"error": True, "message": str(exc)}, status_code=500)


@app.get("/api/campaign-state-live/{campaign_id}")
def api_campaign_state_live(
    campaign_id: str,
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Real-time campaign state straight from Amazon Ads (not the BigQuery-synced
    dashboard, which lags behind live changes by a sync cycle)."""
    verify_internal_token(authorization, x_daily_optimizer_token)
    try:
        client = AmazonAdsClient()
        data = client.post(
            "/sp/campaigns/list",
            {
                "maxResults": 10,
                "campaignIdFilter": {"include": [str(campaign_id)]},
            },
            content_type="application/vnd.spcampaign.v3+json",
            accept="application/vnd.spcampaign.v3+json",
        )
        campaigns = data.get("campaigns", [])
        if not campaigns:
            return JSONResponse({"error": True, "message": "Campaign not found"}, status_code=404)
        return JSONResponse(campaigns[0])
    except Exception as exc:
        return JSONResponse({"error": True, "message": str(exc)}, status_code=500)


@app.get("/api/campaign-products")
def api_campaign_products(limit: int = 50) -> JSONResponse:
    """Product list for the Campaign Builder UI (dashboard's /api/campaigns/products
    proxy calls this). Includes a preview of the campaign each product would
    launch, matching what /api/create-campaign-from-product actually creates."""
    try:
        rows = [r for r in load_products() if r]
        preview = []
        for row in rows[:limit]:
            product = normalized_product(row)
            if not product.get("active", True):
                continue
            keywords = generate_keywords_for_product(row)
            preview.append({
                "sku": product.get("sku", ""),
                "asin": product.get("asin", ""),
                "product_name": product.get("title", "") or product.get("sku", ""),
                "total_keywords": len(keywords),
                "campaign_count": 1,
                "estimated_daily_budget": product.get("suggested_budget"),
            })
        return JSONResponse({"count": len(preview), "products": preview})
    except Exception as exc:
        logger.exception("Failed to build campaign-products preview")
        return JSONResponse({"error": True, "message": str(exc)}, status_code=500)


# ========================= ACOS CIRCUIT BREAKER =========================
# Ceiling now comes from acos_policy.get_circuit_breaker_ceiling() (the
# canonical policy module) instead of a local constant. Deliberately
# independent of daily_budget: the BigQuery-synced daily_budget field has
# been observed stuck at 0.0 for campaigns that are actually ENABLED with a
# real budget on Amazon's side, so budget-based pacing can't be trusted as
# the sole safety net for runaway ACOS. Reads live cost_7d/sales_7d/acos_7d
# from the dashboard's /api/campaigns (verified accurate against Amazon Ads
# directly) rather than any BigQuery daily_budget column.
ACOS_CIRCUIT_BREAKER_MIN_SPEND = 20.0  # ignore low-spend noise (e.g. 1 click, no sales yet)
DASHBOARD_CAMPAIGNS_URL = os.getenv(
    "DASHBOARD_CAMPAIGNS_URL",
    "https://amazon-ppc-dashboard-366028971954.us-central1.run.app/api/campaigns",
)


@app.post("/api/acos-circuit-breaker")
def api_acos_circuit_breaker(
    payload: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Pause any ENABLED campaign whose trailing ACOS exceeds the canonical
    circuit-breaker ceiling, regardless of daily_budget/pacing state."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    from acos_policy import get_circuit_breaker_ceiling

    apply_live = bool(payload.get("apply_live", False))
    ceiling = float(payload.get("acos_ceiling", get_circuit_breaker_ceiling()))
    min_spend = float(payload.get("min_spend", ACOS_CIRCUIT_BREAKER_MIN_SPEND))

    try:
        resp = requests.get(DASHBOARD_CAMPAIGNS_URL, timeout=30)
        resp.raise_for_status()
        campaigns = resp.json().get("campaigns", [])
    except Exception as exc:
        logger.exception("ACOS circuit breaker: failed to fetch campaign performance")
        return JSONResponse({"error": True, "message": f"Failed to fetch campaign performance: {exc}"}, status_code=502)

    client = AmazonAdsClient() if apply_live else None
    flagged: List[Dict[str, Any]] = []

    for c in campaigns:
        if c.get("state") != "ENABLED":
            continue
        acos = c.get("acos_7d")
        cost = float(c.get("cost_7d") or 0)
        if acos is None or acos <= ceiling or cost < min_spend:
            continue

        campaign_id = c["campaign_id"]
        campaign_name = c.get("campaign_name", "")
        entry = {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "acos_7d": acos,
            "cost_7d": cost,
            "sales_7d": c.get("sales_7d"),
            "ceiling": ceiling,
            "action": "would_pause",
        }

        if apply_live:
            try:
                client.put(
                    "/sp/campaigns",
                    {"campaigns": [{"campaignId": str(campaign_id), "state": "PAUSED"}]},
                    content_type="application/vnd.spcampaign.v3+json",
                    accept="application/vnd.spcampaign.v3+json",
                )
                entry["action"] = "paused"
                logger.warning(
                    f"ACOS CIRCUIT BREAKER: paused campaign {campaign_id} ({campaign_name}) "
                    f"acos_7d={acos:.1%} cost_7d=${cost:.2f} ceiling={ceiling:.1%}"
                )
            except Exception as exc:
                entry["action"] = "error"
                entry["error"] = str(exc)
                logger.error(f"ACOS CIRCUIT BREAKER: failed to pause {campaign_id}: {exc}")
        else:
            logger.warning(
                f"ACOS CIRCUIT BREAKER (dry run): would pause campaign {campaign_id} ({campaign_name}) "
                f"acos_7d={acos:.1%} cost_7d=${cost:.2f} ceiling={ceiling:.1%}"
            )

        flagged.append(entry)

    return JSONResponse({
        "apply_live": apply_live,
        "ceiling": ceiling,
        "min_spend": min_spend,
        "campaigns_checked": len(campaigns),
        "flagged_count": len(flagged),
        "flagged": flagged,
    })


# ========================= ACOS CIRCUIT BREAKER V2 (2026-07-16) =========================
# Runs alongside (does not replace) /api/acos-circuit-breaker above. That one
# still enforces the flat 38% pause-on-sight safety net; per the consolidation
# plan's safety invariant, it stays live until this replacement has been
# verified. v2 adds what the flat version can't do:
#   - per-campaign tiered ceilings (products.target_acos, conservative default)
#   - 3-day AND 7-day trailing windows (catches a fast blowup before it
#     accumulates 7 days of damage)
#   - floors bids instead of pausing outright (campaign stays live, traffic
#     just collapses toward zero - a smaller swing than a full stop)
#   - persists trip state so a tripped campaign is never silently re-evaluated
#     and un-flagged without a human clearing it
#   - Slack alerting
#   - a separate daily-budget pacing check independent of ACOS
CIRCUIT_BREAKER_V2_MIN_SPEND = 20.0  # same noise floor as v1


def _tripped_uncleared_campaign_ids(client) -> set:
    rows = client.query(
        f"""
        SELECT DISTINCT campaign_id
        FROM `amazon-ppc-bid-optimizer.amazon_ppc.circuit_breaker_state`
        WHERE cleared IS NOT TRUE
        """
    ).result()
    return {str(r.campaign_id) for r in rows}


def _campaign_performance_windows(client) -> Dict[str, Dict[str, Any]]:
    query = """
        SELECT
          campaign_id,
          MAX(campaign_name) AS campaign_name,
          MAX(campaign_status) AS state,
          SUM(IF(date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY), cost, 0)) AS cost_3d,
          SUM(IF(date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY), sales, 0)) AS sales_3d,
          SUM(IF(date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY), cost, 0)) AS cost_7d,
          SUM(IF(date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY), sales, 0)) AS sales_7d
        FROM `amazon-ppc-bid-optimizer.amazon_ppc.sp_campaign_performance`
        GROUP BY campaign_id
        HAVING UPPER(state) = 'ENABLED'
    """
    out = {}
    for r in client.query(query).result():
        out[str(r.campaign_id)] = {
            "campaign_name": r.campaign_name,
            "cost_3d": float(r.cost_3d or 0),
            "sales_3d": float(r.sales_3d or 0),
            "cost_7d": float(r.cost_7d or 0),
            "sales_7d": float(r.sales_7d or 0),
        }
    return out


def _record_trip(bq_client, campaign_id: str, campaign_name: str, reason: str, acos_3d, acos_7d, ceiling: float, cost_7d: float, sales_7d: float) -> None:
    from google.cloud import bigquery

    query = """
        INSERT INTO `amazon-ppc-bid-optimizer.amazon_ppc.circuit_breaker_state`
        (campaign_id, campaign_name, tripped_at, reason, acos_3d, acos_7d, ceiling, cost_7d, sales_7d, cleared, cleared_at)
        VALUES (@campaign_id, @campaign_name, CURRENT_TIMESTAMP(), @reason, @acos_3d, @acos_7d, @ceiling, @cost_7d, @sales_7d, FALSE, NULL)
    """
    params = [
        bigquery.ScalarQueryParameter("campaign_id", "STRING", str(campaign_id)),
        bigquery.ScalarQueryParameter("campaign_name", "STRING", campaign_name or ""),
        bigquery.ScalarQueryParameter("reason", "STRING", reason),
        bigquery.ScalarQueryParameter("acos_3d", "FLOAT64", acos_3d),
        bigquery.ScalarQueryParameter("acos_7d", "FLOAT64", acos_7d),
        bigquery.ScalarQueryParameter("ceiling", "FLOAT64", ceiling),
        bigquery.ScalarQueryParameter("cost_7d", "FLOAT64", cost_7d),
        bigquery.ScalarQueryParameter("sales_7d", "FLOAT64", sales_7d),
    ]
    bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()


def pct_or_inf(v: Optional[float]) -> str:
    return f"{v:.1%}" if v is not None else "inf (zero sales)"


def _floor_all_bids(client: AmazonAdsClient, campaign_id: str) -> int:
    from acos_policy import CIRCUIT_BREAKER_FLOOR_BID

    keywords = client.list_keywords(campaign_id)
    rows = [
        {"keywordId": kw["keywordId"], "bid": CIRCUIT_BREAKER_FLOOR_BID, "state": "ENABLED"}
        for kw in keywords
        if kw.get("keywordId")
    ]
    if rows:
        client.update_keywords(rows)
    return len(rows)


@app.post("/api/acos-circuit-breaker-v2")
def api_acos_circuit_breaker_v2(
    payload: Dict[str, Any] = Body(default={}),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Tiered, dual-window ACOS circuit breaker. See module comment above
    for how this differs from /api/acos-circuit-breaker."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    from google.cloud import bigquery
    from acos_policy import get_all_campaign_acos_ceilings
    from alerting import send_slack_alert

    apply_live = bool(payload.get("apply_live", False))
    min_spend = float(payload.get("min_spend", CIRCUIT_BREAKER_V2_MIN_SPEND))

    bq_client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))

    try:
        windows = _campaign_performance_windows(bq_client)
        already_tripped = _tripped_uncleared_campaign_ids(bq_client)
        ceilings = get_all_campaign_acos_ceilings()
    except Exception as exc:
        logger.exception("ACOS circuit breaker v2: failed to fetch campaign performance")
        return JSONResponse({"error": True, "message": f"Failed to fetch campaign performance: {exc}"}, status_code=502)

    ads_client = AmazonAdsClient() if apply_live else None
    live_campaigns_by_id: Dict[str, Any] = {}
    if apply_live:
        try:
            live_campaigns_by_id = {str(c.get("campaignId")): c for c in ads_client.list_campaigns()}
        except Exception as exc:
            logger.warning(f"ACOS circuit breaker v2: failed to fetch live campaign list for budget check: {exc}")

    newly_tripped: List[Dict[str, Any]] = []
    budget_alerts: List[Dict[str, Any]] = []
    skipped_already_tripped = 0

    for campaign_id, perf in windows.items():
        cost_7d = perf["cost_7d"]
        sales_7d = perf["sales_7d"]
        campaign_name = perf["campaign_name"] or ""

        if campaign_id in already_tripped:
            skipped_already_tripped += 1
            continue

        if cost_7d < min_spend:
            continue

        ceiling = ceilings.get(campaign_id, 0.25)
        acos_3d = round(perf["cost_3d"] / perf["sales_3d"], 4) if perf["sales_3d"] > 0 else None
        acos_7d = round(cost_7d / sales_7d, 4) if sales_7d > 0 else None

        # Zero sales with real spend is the worst case (infinite ACOS) and
        # must trip regardless of the None guard above.
        acos_3d_breach = (acos_3d is not None and acos_3d > ceiling) or (perf["sales_3d"] == 0 and perf["cost_3d"] >= min_spend)
        acos_7d_breach = (acos_7d is not None and acos_7d > ceiling) or (sales_7d == 0 and cost_7d >= min_spend)

        if acos_3d_breach or acos_7d_breach:
            reason = (
                f"3d ACOS {('%.1f%%' % (acos_3d * 100)) if acos_3d is not None else 'inf (zero sales)'} "
                f"or 7d ACOS {('%.1f%%' % (acos_7d * 100)) if acos_7d is not None else 'inf (zero sales)'} "
                f"exceeded ceiling {ceiling:.1%}"
            )
            bids_floored = 0
            if apply_live:
                try:
                    bids_floored = _floor_all_bids(ads_client, campaign_id)
                except Exception as exc:
                    logger.error(f"ACOS circuit breaker v2: failed to floor bids for {campaign_id}: {exc}")

            try:
                _record_trip(bq_client, campaign_id, campaign_name, reason, acos_3d, acos_7d, ceiling, cost_7d, sales_7d)
            except Exception as exc:
                logger.error(f"ACOS circuit breaker v2: failed to record trip for {campaign_id}: {exc}")

            alert_msg = (
                f"🔴 ACOS CIRCUIT BREAKER TRIPPED\n"
                f"Campaign: {campaign_name} ({campaign_id})\n"
                f"3d ACOS: {pct_or_inf(acos_3d)}  ·  7d ACOS: {pct_or_inf(acos_7d)}  ·  Ceiling: {ceiling:.1%}\n"
                f"7d cost: ${cost_7d:.2f}  ·  7d sales: ${sales_7d:.2f}\n"
                f"Action: {'bids floored to $%.2f (' % 0.02 + str(bids_floored) + ' keywords)' if apply_live else 'DRY RUN - no bids changed'}\n"
                f"Will NOT auto-resume. Clear manually via /api/acos-circuit-breaker/clear/{campaign_id}."
            )
            send_slack_alert(alert_msg)

            newly_tripped.append({
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "acos_3d": acos_3d,
                "acos_7d": acos_7d,
                "ceiling": ceiling,
                "cost_7d": cost_7d,
                "sales_7d": sales_7d,
                "bids_floored": bids_floored,
                "apply_live": apply_live,
            })
            continue

        # Budget pacing check - independent of ACOS, only for campaigns that
        # didn't already trip the ACOS breaker above.
        live_campaign = live_campaigns_by_id.get(campaign_id)
        if live_campaign:
            live_budget = float((live_campaign.get("budget") or {}).get("budget") or 0)
            avg_daily_cost = cost_7d / 7.0
            if live_budget > 0 and avg_daily_cost > live_budget * 2:
                budget_alerts.append({
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "avg_daily_cost_7d": round(avg_daily_cost, 2),
                    "daily_budget": live_budget,
                })
                send_slack_alert(
                    f"🟡 BUDGET PACING ALARM\n"
                    f"Campaign: {campaign_name} ({campaign_id})\n"
                    f"Averaging ${avg_daily_cost:.2f}/day over the last 7 days against a ${live_budget:.2f} daily budget "
                    f"({avg_daily_cost / live_budget:.1f}x). No bid action taken - budget/pacing issue, not an ACOS issue."
                )

    return JSONResponse({
        "apply_live": apply_live,
        "min_spend": min_spend,
        "campaigns_checked": len(windows),
        "skipped_already_tripped": skipped_already_tripped,
        "newly_tripped_count": len(newly_tripped),
        "newly_tripped": newly_tripped,
        "budget_alerts_count": len(budget_alerts),
        "budget_alerts": budget_alerts,
    })


@app.post("/api/acos-circuit-breaker/clear/{campaign_id}")
def api_clear_circuit_breaker(
    campaign_id: str,
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Human-only unflag. Does NOT restore bids or resume the campaign -
    that's a separate, deliberate decision for whoever clears this to make
    afterward with full context on why it tripped."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    from google.cloud import bigquery

    client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))
    query = """
        UPDATE `amazon-ppc-bid-optimizer.amazon_ppc.circuit_breaker_state`
        SET cleared = TRUE, cleared_at = CURRENT_TIMESTAMP()
        WHERE campaign_id = @campaign_id AND cleared IS NOT TRUE
    """
    params = [bigquery.ScalarQueryParameter("campaign_id", "STRING", str(campaign_id))]
    job = client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params))
    job.result()

    if job.num_dml_affected_rows == 0:
        return JSONResponse({"error": True, "message": f"No uncleared trip found for campaign {campaign_id}"}, status_code=404)

    return JSONResponse({"success": True, "campaign_id": campaign_id, "cleared": True})


# ========================= amazon-ppc-api REPLACEMENT ENDPOINTS =========================
# amazon-ppc-api (image us-central1-docker.pkg.dev/.../ppc/amazon-ppc-api) has no
# recoverable source (6+ months stale, pushed via raw docker push, no GitHub repo,
# no Cloud Build history). These reimplement its load-bearing routes so callers can
# be migrated off it. Do not delete that service until every caller here is
# confirmed cut over (check Cloud Run IAM bindings, not just code references).

@app.get("/api/settings")
def api_settings() -> JSONResponse:
    """Replaces amazon-ppc-api's /api/settings, which read target_acos from the
    same amazon_ppc.optimizer_config table this reads from directly."""
    from acos_policy import get_target_acos, get_circuit_breaker_ceiling
    return JSONResponse({
        "target_acos": get_target_acos(),
        "circuit_breaker_ceiling": get_circuit_breaker_ceiling(),
    })


@app.get("/api/budgets")
def api_budgets(
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Replaces amazon-ppc-api's /api/budgets, which read daily_budget from
    amazon_ppc.campaigns - a table confirmed abandoned (313/313 rows NULL,
    no writer for 3+ days as of this session). Reads sp_campaign_performance
    instead, the table ads-data-sync actually keeps current."""
    verify_internal_token(authorization, x_daily_optimizer_token)
    from google.cloud import bigquery

    client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))
    query = """
        SELECT campaign_id, campaign_name, campaign_status AS state,
               campaign_budget AS daily_budget, cost AS spend_today, date,
               date = CURRENT_DATE() AS is_today
        FROM `amazon-ppc-bid-optimizer.amazon_ppc.sp_campaign_performance`
        QUALIFY ROW_NUMBER() OVER (PARTITION BY campaign_id ORDER BY date DESC) = 1
    """
    rows = [
        {
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "state": row.state,
            "daily_budget": row.daily_budget,
            "spend_today": row.spend_today if row.is_today else None,
            "as_of_date": str(row.date),
        }
        for row in client.query(query).result()
    ]
    return JSONResponse({"campaigns": rows})


@app.put("/api/campaigns/{campaign_id}/state")
def api_update_campaign_state(
    campaign_id: str,
    payload: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Replaces amazon-ppc-api's PUT /api/campaigns/{id}/state, which its own
    OpenAPI description admitted only updated BigQuery ("dashboard only") -
    it never actually called Amazon, so using it to pause a campaign gave a
    false sense of safety. This one really calls Amazon's API, using the
    same pattern proven by /api/acos-circuit-breaker."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    state = str(payload.get("state", "")).upper()
    if state not in ("ENABLED", "PAUSED"):
        return JSONResponse({"error": True, "message": "state must be ENABLED or PAUSED"}, status_code=400)

    try:
        client = AmazonAdsClient()
        client.put(
            "/sp/campaigns",
            {"campaigns": [{"campaignId": str(campaign_id), "state": state}]},
            content_type="application/vnd.spcampaign.v3+json",
            accept="application/vnd.spcampaign.v3+json",
        )
    except Exception as exc:
        logger.error(f"Failed to set campaign {campaign_id} state to {state}: {exc}")
        return JSONResponse({"error": True, "message": str(exc)}, status_code=500)

    return JSONResponse({"success": True, "campaign_id": campaign_id, "state": state})


@app.get("/api/decisions")
def api_decisions(
    limit: int = 200,
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Replaces amazon-ppc-api's /api/decisions, which read
    recommendation_bid_changes - confirmed stopped receiving writes from
    anything but keyword-harvester in January 2026. bid_optimizations is
    where aov_bid_optimizer.py (the job actually producing bid decisions,
    now that its table-name bug is fixed) logs to."""
    verify_internal_token(authorization, x_daily_optimizer_token)
    from google.cloud import bigquery

    client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))
    query = f"""
        SELECT campaign_id, keyword_id, keyword_text, current_bid, new_bid,
               performance_tier, aov_tier, ceiling, reasoning, timestamp
        FROM `amazon-ppc-bid-optimizer.amazon_ppc.bid_optimizations`
        ORDER BY timestamp DESC
        LIMIT {int(limit)}
    """
    rows = [dict(row) for row in client.query(query).result()]
    for row in rows:
        if row.get("timestamp") is not None:
            row["timestamp"] = row["timestamp"].isoformat()
    return JSONResponse({"count": len(rows), "decisions": rows})


# ========================= PRODUCT MANAGEMENT =========================
# Admin CRUD for amazon_ppc.products (the BigQuery table that replaced the
# shared Google Sheet product feed - see optimize_campaigns.py's
# load_products()). GET /api/products (server.py's version, already live)
# lists everything including inactive products; these add the write side.

_PRODUCTS_TABLE = "amazon-ppc-bid-optimizer.amazon_ppc.products"


def _bigquery_client():
    from google.cloud import bigquery
    return bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))


@app.post("/api/products")
def api_create_product(
    payload: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Add a new product to the feed. product_id and sku are required and
    must be unique - callers should pick a stable, human-readable ID
    (e.g. "NWS_029"), not something autogenerated."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    product_id = str(payload.get("product_id", "")).strip()
    sku = str(payload.get("sku", "")).strip()
    if not product_id or not sku:
        return JSONResponse({"error": True, "message": "product_id and sku are required"}, status_code=400)

    from google.cloud import bigquery

    client = _bigquery_client()
    existing = list(client.query(
        f"SELECT product_id FROM `{_PRODUCTS_TABLE}` WHERE product_id = @pid",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("pid", "STRING", product_id)]
        ),
    ).result())
    if existing:
        return JSONResponse({"error": True, "message": f"product_id '{product_id}' already exists"}, status_code=409)

    row = {
        "product_id": product_id,
        "sku": sku,
        "asin": str(payload.get("asin", "")).strip(),
        "title": str(payload.get("title", "")).strip(),
        "selling_price": float(payload["selling_price"]) if payload.get("selling_price") not in (None, "") else None,
        "active": bool(payload.get("active", True)),
        "category": str(payload.get("category", "")).strip(),
        "keywords": str(payload.get("keywords", "")).strip(),
        "research_keywords": str(payload.get("research_keywords", "")).strip(),
        "target_acos": float(payload["target_acos"]) if payload.get("target_acos") not in (None, "") else None,
    }

    # DML INSERT, not the streaming insert_rows_json() API: rows written via
    # streaming go into a buffer that blocks UPDATE/DELETE DML against them
    # for a while afterward (confirmed live: "would affect rows in the
    # streaming buffer, which is not supported"). A customer editing a typo
    # right after adding a product is an expected, common case - DML INSERT
    # avoids the buffer entirely so the row is immediately editable.
    query = f"""
        INSERT INTO `{_PRODUCTS_TABLE}`
        (product_id, sku, asin, title, selling_price, active, category, keywords, research_keywords, target_acos)
        VALUES (@product_id, @sku, @asin, @title, @selling_price, @active, @category, @keywords, @research_keywords, @target_acos)
    """
    params = [
        bigquery.ScalarQueryParameter("product_id", "STRING", row["product_id"]),
        bigquery.ScalarQueryParameter("sku", "STRING", row["sku"]),
        bigquery.ScalarQueryParameter("asin", "STRING", row["asin"]),
        bigquery.ScalarQueryParameter("title", "STRING", row["title"]),
        bigquery.ScalarQueryParameter("selling_price", "FLOAT64", row["selling_price"]),
        bigquery.ScalarQueryParameter("active", "BOOL", row["active"]),
        bigquery.ScalarQueryParameter("category", "STRING", row["category"]),
        bigquery.ScalarQueryParameter("keywords", "STRING", row["keywords"]),
        bigquery.ScalarQueryParameter("research_keywords", "STRING", row["research_keywords"]),
        bigquery.ScalarQueryParameter("target_acos", "FLOAT64", row["target_acos"]),
    ]
    try:
        job = client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params))
        job.result()
    except Exception as exc:
        logger.error(f"Failed to insert product {product_id}: {exc}")
        return JSONResponse({"error": True, "message": str(exc)}, status_code=500)

    # load_products() caches BigQuery results for 15 minutes (optimize_campaigns.py)
    # so GET /api/products would otherwise keep serving the pre-insert list.
    optimize_campaigns._products_cache = None

    return JSONResponse({"success": True, "product": row})


@app.put("/api/products/{product_id}")
def api_update_product(
    product_id: str,
    payload: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Update an existing product. Only fields present in the payload are
    changed; omitted fields keep their current value."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    from google.cloud import bigquery

    editable = ("sku", "asin", "title", "selling_price", "active", "category", "keywords", "research_keywords", "target_acos")
    set_clauses = []
    params = [bigquery.ScalarQueryParameter("pid", "STRING", product_id)]
    for field in editable:
        if field not in payload:
            continue
        value = payload[field]
        if field == "active":
            set_clauses.append(f"{field} = @{field}")
            params.append(bigquery.ScalarQueryParameter(field, "BOOL", bool(value)))
        elif field in ("selling_price", "target_acos"):
            set_clauses.append(f"{field} = @{field}")
            params.append(bigquery.ScalarQueryParameter(field, "FLOAT64", float(value) if value not in (None, "") else None))
        else:
            set_clauses.append(f"{field} = @{field}")
            params.append(bigquery.ScalarQueryParameter(field, "STRING", str(value)))

    if not set_clauses:
        return JSONResponse({"error": True, "message": "No editable fields in payload"}, status_code=400)

    client = _bigquery_client()
    query = f"UPDATE `{_PRODUCTS_TABLE}` SET {', '.join(set_clauses)} WHERE product_id = @pid"
    job = client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params))
    job.result()

    if job.num_dml_affected_rows == 0:
        return JSONResponse({"error": True, "message": f"product_id '{product_id}' not found"}, status_code=404)

    optimize_campaigns._products_cache = None

    return JSONResponse({"success": True, "product_id": product_id, "updated_fields": list(set_clauses)})


# ========================= STACKING RULES CONFIG =========================
# Live-editable config for backend/core/rule_engine.py's stackable bid rules
# (spend cap pause, off-peak bid reduction, weekend bid adjustment, inventory
# days pause). This service only reads/writes the BigQuery-backed config -
# backend/'s bid-optimizer job is what actually evaluates it on each run.

from stacking_rules_store import InvalidRuleError, RULE_TYPE_METADATA, get_rules, save_rules  # noqa: E402


@app.get("/api/stacking-rules/types")
def api_stacking_rule_types(
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Available rule types and their param schema, for the UI to render
    forms without hardcoding rule shapes on the frontend."""
    verify_internal_token(authorization, x_daily_optimizer_token)
    return JSONResponse({"types": RULE_TYPE_METADATA})


@app.get("/api/stacking-rules")
def api_get_stacking_rules(
    scope: str = "default",
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Rules saved for one scope ('default' or a campaign_id). Does not fall
    back to a different scope - that fallback (campaign -> default -> bundled
    JSON) is the bid optimizer's read-time behavior; this endpoint reports
    exactly what's saved for the scope asked about, so a blank campaign-level
    config in the UI reads as blank, not silently inherited."""
    verify_internal_token(authorization, x_daily_optimizer_token)
    rules = get_rules(scope)
    return JSONResponse({"scope": scope, "rules": rules})


@app.put("/api/stacking-rules")
def api_put_stacking_rules(
    payload: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
    x_daily_optimizer_token: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Save a rule list for a scope ('default' or a campaign_id), replacing
    whatever was there. Body: {"scope": "default" | "<campaign_id>", "rules": [...]}."""
    verify_internal_token(authorization, x_daily_optimizer_token)

    scope = str(payload.get("scope") or "default")
    rules = payload.get("rules")
    if rules is None:
        return JSONResponse({"error": True, "message": "'rules' is required"}, status_code=400)

    try:
        save_rules(scope, rules)
    except InvalidRuleError as exc:
        return JSONResponse({"error": True, "message": str(exc)}, status_code=400)
    except Exception as exc:
        logger.exception(f"Failed to save stacking rules for scope '{scope}'")
        return JSONResponse({"error": True, "message": f"Failed to save: {exc}"}, status_code=502)

    return JSONResponse({"success": True, "scope": scope, "rules": rules})

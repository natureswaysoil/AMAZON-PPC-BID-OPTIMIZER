export const dynamic = 'force-dynamic';

import { NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

const bigquery = new BigQuery({
  projectId: 'amazon-ppc-bid-optimizer',
});

export async function GET() {
  try {
    // Queries the real sync tables written by the ads_sync job (dataset: amazon_ppc).
    // Only returns campaigns whose most recent status is ENABLED (active).
    const query = `
      SELECT
        cp.campaign_id,
        cp.campaign_name,
        MAX(cp.campaign_status)  AS state,
        MAX(cp.campaign_budget)  AS daily_budget,
        'MANUAL'                 AS targeting_type,
        MAX(cp.updated_at)       AS updated_at,
        COUNT(DISTINCT kp.keyword_id) AS keyword_count,
        COALESCE(SUM(IF(cp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY), cp.cost, 0)), 0)      AS cost_7d,
        COALESCE(SUM(IF(cp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY), cp.sales, 0)), 0) AS sales_7d,
        SAFE_DIVIDE(
          SUM(IF(cp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY), cp.cost, 0)),
          NULLIF(SUM(IF(cp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY), cp.sales, 0)), 0)
        ) AS acos_7d
      FROM \`amazon-ppc-bid-optimizer.amazon_ppc.sp_campaign_performance\` cp
      LEFT JOIN \`amazon-ppc-bid-optimizer.amazon_ppc.sp_keyword_performance\` kp
        ON cp.campaign_id = kp.campaign_id
      GROUP BY cp.campaign_id, cp.campaign_name
      HAVING UPPER(MAX(cp.campaign_status)) = 'ENABLED'
      ORDER BY cost_7d DESC
    `;

    const [rows] = await bigquery.query({ query });

    console.log(`Found ${rows.length} campaigns`);

    return NextResponse.json({
      campaigns: rows,
      count: rows.length,
    });
  } catch (error: any) {
    console.error('Campaign query failed:', error);
    return NextResponse.json({
      error: error.message,
      campaigns: [],
    }, { status: 500 });
  }
}

export const dynamic = 'force-dynamic';
import { NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

const bigquery = new BigQuery({
  projectId: 'amazon-ppc-bid-optimizer',
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const campaignIdParam = searchParams.get('campaign_id');

  // Validate campaign_id is an integer before using it in a query.
  const campaignId =
    campaignIdParam !== null && /^\d+$/.test(campaignIdParam)
      ? parseInt(campaignIdParam, 10)
      : null;

  try {
    // Queries the real sync table written by the ads_sync job (dataset: amazon_ppc).
    const query = `
      SELECT
        kp.keyword_id,
        kp.keyword_text,
        kp.match_type,
        kp.keyword_bid                  AS current_bid,
        'ACTIVE'                        AS state,
        kp.campaign_name,
        kp.clicks                       AS clicks_30d,
        kp.purchases                    AS conversions_30d,
        kp.cost                         AS cost_30d,
        kp.sales                        AS sales_30d,
        kp.acos,
        NULL                            AS suggested_bid,
        NULL                            AS aov_tier,
        NULL                            AS performance_tier,
        NULL                            AS reasoning
      FROM \`amazon-ppc-bid-optimizer.amazon_ppc.sp_keyword_performance\` kp
      ${campaignId !== null ? `WHERE kp.campaign_id = ${campaignId}` : ''}
      ORDER BY kp.cost DESC
    `;

    const [rows] = await bigquery.query({ query });

    console.log(`Found ${rows.length} keywords`);

    return NextResponse.json({
      keywords: rows,
      count: rows.length,
    });
  } catch (error: any) {
    console.error('Keywords query failed:', error);
    return NextResponse.json({
      error: error.message,
      keywords: [],
    }, { status: 500 });
  }
}

export const dynamic = 'force-dynamic';
import { NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

const bigquery = new BigQuery({
  projectId: 'amazon-ppc-bid-optimizer',
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const campaignId = searchParams.get('campaign_id');

  try {
    const query = `
      SELECT 
        k.keyword_id,
        k.keyword_text,
        k.match_type,
        k.bid as current_bid,
        k.state,
        c.campaign_name,
        COALESCE(SUM(dp.clicks), 0) as clicks_30d,
        COALESCE(SUM(dp.conversions), 0) as conversions_30d,
        COALESCE(SUM(dp.cost), 0) as cost_30d,
        COALESCE(SUM(dp.sales), 0) as sales_30d,
        SAFE_DIVIDE(SUM(dp.cost), NULLIF(SUM(dp.sales), 0)) as acos,
        opt.new_bid as suggested_bid,
        opt.aov_tier,
        opt.performance_tier,
        opt.reasoning
      FROM \`amazon-ppc-bid-optimizer.amazon_data.keywords\` k
      JOIN \`amazon-ppc-bid-optimizer.amazon_data.campaigns\` c 
        ON k.campaign_id = c.campaign_id
      LEFT JOIN \`amazon-ppc-bid-optimizer.amazon_data.daily_performance\` dp 
        ON k.keyword_id = dp.keyword_id
        AND dp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
      LEFT JOIN \`amazon-ppc-bid-optimizer.amazon_data.optimizer_dashboard\` opt
        ON k.keyword_text = opt.keyword_text
      ${campaignId ? `WHERE k.campaign_id = ${campaignId}` : 'WHERE k.keyword_id >= 2000'}
      GROUP BY k.keyword_id, k.keyword_text, k.match_type, k.bid, k.state, 
               c.campaign_name, opt.new_bid, opt.aov_tier, opt.performance_tier, opt.reasoning
      ORDER BY cost_30d DESC
    `;

    const [rows] = await bigquery.query({ query });
    
    console.log(`Found ${rows.length} keywords`);
    
    return NextResponse.json({ 
      keywords: rows,
      count: rows.length
    });
  } catch (error: any) {
    console.error('Keywords query failed:', error);
    return NextResponse.json({ 
      error: error.message,
      keywords: [] 
    }, { status: 500 });
  }
}

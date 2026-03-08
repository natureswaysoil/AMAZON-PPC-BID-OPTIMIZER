export const dynamic = 'force-dynamic';

import { NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

const bigquery = new BigQuery({
  projectId: 'amazon-ppc-bid-optimizer',
});

export async function GET() {
  try {
    const query = `
      SELECT 
        c.campaign_id,
        c.campaign_name,
        c.state,
        c.daily_budget,
        c.targeting_type,
        c.updated_at,
        COUNT(DISTINCT k.keyword_id) as keyword_count,
        COALESCE(SUM(dp.cost), 0) as cost_7d,
        COALESCE(SUM(dp.sales), 0) as sales_7d,
        SAFE_DIVIDE(SUM(dp.cost), NULLIF(SUM(dp.sales), 0)) as acos_7d
      FROM \`amazon-ppc-bid-optimizer.amazon_data.campaigns\` c
      LEFT JOIN \`amazon-ppc-bid-optimizer.amazon_data.keywords\` k 
        ON c.campaign_id = k.campaign_id
      LEFT JOIN \`amazon-ppc-bid-optimizer.amazon_data.daily_performance\` dp 
        ON k.keyword_id = dp.keyword_id
        AND dp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
      GROUP BY c.campaign_id, c.campaign_name, c.state, c.daily_budget, c.targeting_type, c.updated_at
      ORDER BY c.updated_at DESC
    `;

    console.log('Executing query:', query);
    
    const [rows] = await bigquery.query({ query });
    
    console.log(`Found ${rows.length} campaigns`);
    
    return NextResponse.json({ 
      campaigns: rows,
      count: rows.length,
      query: query
    });
  } catch (error: any) {
    console.error('Campaign query failed:', error);
    return NextResponse.json({ 
      error: error.message,
      stack: error.stack,
      campaigns: [] 
    }, { status: 500 });
  }
}

# backend/jobs/alerts/alert_engine.py
from google.cloud import bigquery
from backend.core.config import settings
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class AlertEngine:
    """
    Smart alerting system that only sends notifications for actionable issues
    """
    
    def __init__(self):
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        
        # Alert thresholds (can be overridden per client)
        self.thresholds = {
            'acos_spike': 1.5,  # 50% increase
            'cvr_drop': 0.7,    # 30% decrease
            'inventory_warning_days': 7,
            'budget_pace_threshold': 1.3,  # 30% over pace
            'min_spend_for_alert': 10.0
        }
    
    def check_acos_spikes(self) -> List[Dict]:
        """Alert when ACOS increases significantly"""
        query = """
        WITH daily_acos AS (
          SELECT 
            campaign_id,
            campaign_name,
            asin,
            date,
            SAFE_DIVIDE(SUM(cost), SUM(sales)) as acos,
            SUM(cost) as cost
          FROM `{project}.{dataset}.daily_performance` dp
          JOIN `{project}.{dataset}.campaigns` c USING (campaign_id)
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
          GROUP BY campaign_id, campaign_name, asin, date
        ),
        acos_comparison AS (
          SELECT 
            campaign_id,
            campaign_name,
            asin,
            AVG(CASE WHEN date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY) 
                THEN acos END) as acos_recent,
            AVG(CASE WHEN date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 10 DAY) 
                                   AND DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
                THEN acos END) as acos_baseline,
            SUM(CASE WHEN date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY) 
                THEN cost END) as recent_spend
          FROM daily_acos
          GROUP BY campaign_id, campaign_name, asin
        )
        SELECT 
          campaign_id,
          campaign_name,
          asin,
          acos_recent,
          acos_baseline,
          recent_spend,
          SAFE_DIVIDE(acos_recent, acos_baseline) as acos_ratio
        FROM acos_comparison
        WHERE 
          acos_baseline > 0
          AND acos_recent > 0
          AND recent_spend >= @min_spend
          AND SAFE_DIVIDE(acos_recent, acos_baseline) >= @threshold
        ORDER BY acos_ratio DESC
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("threshold", "FLOAT64", self.thresholds['acos_spike']),
                bigquery.ScalarQueryParameter("min_spend", "FLOAT64", self.thresholds['min_spend_for_alert'])
            ]
        )
        
        results = self.bq_client.query(query, job_config=job_config).result()
        
        alerts = []
        for row in results:
            alerts.append({
                'alert_type': 'ACOS_SPIKE',
                'severity': 'HIGH' if row['acos_ratio'] >= 2.0 else 'MEDIUM',
                'entity_type': 'CAMPAIGN',
                'entity_id': str(row['campaign_id']),
                'message': f"ACOS increased {(row['acos_ratio']-1)*100:.0f}% for {row['campaign_name']}",
                'data': {
                    'campaign_name': row['campaign_name'],
                    'asin': row['asin'],
                    'acos_baseline': f"{row['acos_baseline']:.1%}",
                    'acos_recent': f"{row['acos_recent']:.1%}",
                    'recent_spend': f"${row['recent_spend']:.2f}"
                },
                'action_items': [
                    'Check for listing changes or Buy Box loss',
                    'Review recent keyword bid changes',
                    'Consider reducing bids if ACOS continues to rise'
                ]
            })
        
        return alerts
    
    def check_conversion_rate_drops(self) -> List[Dict]:
        """Alert when conversion rate drops significantly"""
        query = """
        WITH daily_cvr AS (
          SELECT 
            asin,
            p.title as product_name,
            date,
            SAFE_DIVIDE(SUM(orders), SUM(clicks)) as cvr,
            SUM(clicks) as clicks
          FROM `{project}.{dataset}.daily_performance` dp
          JOIN `{project}.{dataset}.products` p USING (asin)
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
          GROUP BY asin, p.title, date
        ),
        cvr_comparison AS (
          SELECT 
            asin,
            product_name,
            AVG(CASE WHEN date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY) 
                THEN cvr END) as cvr_recent,
            AVG(CASE WHEN date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 10 DAY) 
                                   AND DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
                THEN cvr END) as cvr_baseline,
            SUM(CASE WHEN date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY) 
                THEN clicks END) as recent_clicks
          FROM daily_cvr
          GROUP BY asin, product_name
        )
        SELECT *,
          SAFE_DIVIDE(cvr_recent, cvr_baseline) as cvr_ratio
        FROM cvr_comparison
        WHERE 
          cvr_baseline > 0
          AND recent_clicks >= 20
          AND SAFE_DIVIDE(cvr_recent, cvr_baseline) <= @threshold
        ORDER BY cvr_ratio ASC
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("threshold", "FLOAT64", self.thresholds['cvr_drop'])
            ]
        )
        
        results = self.bq_client.query(query, job_config=job_config).result()
        
        alerts = []
        for row in results:
            alerts.append({
                'alert_type': 'CVR_DROP',
                'severity': 'HIGH' if row['cvr_ratio'] <= 0.5 else 'MEDIUM',
                'entity_type': 'ASIN',
                'entity_id': row['asin'],
                'message': f"Conversion rate dropped {(1-row['cvr_ratio'])*100:.0f}% for {row['product_name']}",
                'data': {
                    'product_name': row['product_name'],
                    'cvr_baseline': f"{row['cvr_baseline']:.2%}",
                    'cvr_recent': f"{row['cvr_recent']:.2%}",
                    'recent_clicks': row['recent_clicks']
                },
                'action_items': [
                    'Check product reviews for negative sentiment',
                    'Verify listing content hasn\'t changed',
                    'Check competitor pricing',
                    'Review main image and A+ content'
                ]
            })
        
        return alerts
    
    def check_inventory_alerts(self) -> List[Dict]:
        """Alert on low inventory that could impact ads"""
        query = """
        WITH inventory_performance AS (
          SELECT 
            i.asin,
            p.title as product_name,
            i.available_quantity,
            i.days_of_cover,
            SUM(dp.cost) as daily_ad_spend_7d
          FROM `{project}.{dataset}.inventory` i
          JOIN `{project}.{dataset}.products` p USING (asin)
          LEFT JOIN `{project}.{dataset}.daily_performance` dp 
            ON i.asin = dp.asin 
            AND dp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
          WHERE i.snapshot_date = CURRENT_DATE()
          GROUP BY i.asin, p.title, i.available_quantity, i.days_of_cover
        )
        SELECT *
        FROM inventory_performance
        WHERE 
          days_of_cover IS NOT NULL
          AND days_of_cover <= @warning_days
          AND daily_ad_spend_7d > 0
        ORDER BY days_of_cover ASC
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("warning_days", "INT64", 
                                             self.thresholds['inventory_warning_days'])
            ]
        )
        
        results = self.bq_client.query(query, job_config=job_config).result()
        
        alerts = []
        for row in results:
            alerts.append({
                'alert_type': 'LOW_INVENTORY',
                'severity': 'CRITICAL' if row['days_of_cover'] <= 3 else 'HIGH',
                'entity_type': 'ASIN',
                'entity_id': row['asin'],
                'message': f"Only {row['days_of_cover']:.0f} days of inventory for {row['product_name']}",
                'data': {
                    'product_name': row['product_name'],
                    'available_quantity': row['available_quantity'],
                    'days_of_cover': f"{row['days_of_cover']:.1f}",
                    'daily_ad_spend': f"${row['daily_ad_spend_7d']/7:.2f}"
                },
                'action_items': [
                    'Consider reducing ad spend to extend runway',
                    'Check inbound shipment status',
                    'Pause ads if stockout is imminent'
                ]
            })
        
        return alerts
    
    def check_budget_pacing(self) -> List[Dict]:
        """Alert when campaigns are overspending too early in the day"""
        query = """
        WITH today_spend AS (
          SELECT 
            c.campaign_id,
            c.campaign_name,
            c.daily_budget,
            SUM(hp.cost) as spend_so_far,
            MAX(hp.hour) as current_hour
          FROM `{project}.{dataset}.hourly_performance` hp
          JOIN `{project}.{dataset}.campaigns` c USING (campaign_id)
          WHERE DATE(hp.timestamp) = CURRENT_DATE()
          GROUP BY c.campaign_id, c.campaign_name, c.daily_budget
        )
        SELECT 
          *,
          SAFE_DIVIDE(spend_so_far, daily_budget) as budget_consumed_pct,
          SAFE_DIVIDE(current_hour, 24) as day_elapsed_pct,
          SAFE_DIVIDE(
            SAFE_DIVIDE(spend_so_far, daily_budget),
            SAFE_DIVIDE(current_hour, 24)
          ) as pace_ratio
        FROM today_spend
        WHERE 
          daily_budget > 0
          AND current_hour >= 6  -- Only alert after 6am
          AND SAFE_DIVIDE(
            SAFE_DIVIDE(spend_so_far, daily_budget),
            SAFE_DIVIDE(current_hour, 24)
          ) >= @threshold
        ORDER BY pace_ratio DESC
        """.format(project=settings.PROJECT_ID, dataset=settings.BIGQUERY_DATASET)
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("threshold", "FLOAT64", 
                                             self.thresholds['budget_pace_threshold'])
            ]
        )
        
        results = self.bq_client.query(query, job_config=job_config).result()
        
        alerts = []
        for row in results:
            alerts.append({
                'alert_type': 'BUDGET_OVERPACE',
                'severity': 'MEDIUM',
                'entity_type': 'CAMPAIGN',
                'entity_id': str(row['campaign_id']),
                'message': f"Campaign overpacing budget by {(row['pace_ratio']-1)*100:.0f}%",
                'data': {
                    'campaign_name': row['campaign_name'],
                    'daily_budget': f"${row['daily_budget']:.2f}",
                    'spend_so_far': f"${row['spend_so_far']:.2f}",
                    'budget_consumed': f"{row['budget_consumed_pct']:.1%}",
                    'day_elapsed': f"{row['day_elapsed_pct']:.1%}"
                },
                'action_items': [
                    'Budget will be exhausted early',
                    'Consider increasing daily budget',
                    'Or reduce bids to slow spend'
                ]
            })
        
        return alerts
    
    def check_competitor_alerts(self) -> List[Dict]:
        """Alert on significant competitor price changes"""
        # This would require competitor tracking data
        # Placeholder for future implementation
        return []
    
    def run_all_checks(self) -> Dict:
        """Run all alert checks and consolidate results"""
        logger.info("Running alert checks")
        
        all_alerts = []
        
        # Run each check
        all_alerts.extend(self.check_acos_spikes())
        all_alerts.extend(self.check_conversion_rate_drops())
        all_alerts.extend(self.check_inventory_alerts())
        all_alerts.extend(self.check_budget_pacing())
        
        # Add metadata
        for alert in all_alerts:
            alert['alert_id'] = f"{alert['alert_type']}_{alert['entity_id']}_{int(datetime.now().timestamp())}"
            alert['timestamp'] = datetime.utcnow().isoformat()
            alert['status'] = 'NEW'
        
        # Save to BigQuery
        if all_alerts:
            self._save_alerts(all_alerts)
        
        logger.info(f"Generated {len(all_alerts)} alerts")
        
        return {
            'total_alerts': len(all_alerts),
            'by_severity': {
                'CRITICAL': len([a for a in all_alerts if a['severity'] == 'CRITICAL']),
                'HIGH': len([a for a in all_alerts if a['severity'] == 'HIGH']),
                'MEDIUM': len([a for a in all_alerts if a['severity'] == 'MEDIUM']),
            },
            'alerts': all_alerts
        }
    
    def _save_alerts(self, alerts: List[Dict]):
        """Save alerts to BigQuery"""
        table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.alerts"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
        )
        
        job = self.bq_client.load_table_from_json(alerts, table_id, job_config=job_config)
        job.result()

# backend/jobs/alerts/notification_sender.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class NotificationSender:
    """Send alert notifications via email, Slack, etc."""
    
    def __init__(self):
        # Email config would come from secrets
        pass
    
    def send_email_alert(self, alerts: List[Dict], recipient: str):
        """Send consolidated email with all alerts"""
        if not alerts:
            return
        
        # Group by severity
        critical = [a for a in alerts if a['severity'] == 'CRITICAL']
        high = [a for a in alerts if a['severity'] == 'HIGH']
        medium = [a for a in alerts if a['severity'] == 'MEDIUM']
        
        html_body = self._generate_email_html(critical, high, medium)
        
        # Send email (implementation depends on your email provider)
        logger.info(f"Would send email to {recipient} with {len(alerts)} alerts")
    
    def _generate_email_html(self, critical: List, high: List, medium: List) -> str:
        """Generate HTML email body"""
        html = """
        <html>
          <head>
            <style>
              .critical { background-color: #ff4444; color: white; }
              .high { background-color: #ff8800; color: white; }
              .medium { background-color: #ffbb33; color: black; }
              .alert-box { margin: 10px; padding: 15px; border-radius: 5px; }
            </style>
          </head>
          <body>
            <h1>Amazon PPC Alerts</h1>
        """
        
        if critical:
            html += "<h2>🚨 Critical Alerts</h2>"
            for alert in critical:
                html += self._format_alert_html(alert, 'critical')
        
        if high:
            html += "<h2>⚠️ High Priority Alerts</h2>"
            for alert in high:
                html += self._format_alert_html(alert, 'high')
        
        if medium:
            html += "<h2>ℹ️ Medium Priority Alerts</h2>"
            for alert in medium:
                html += self._format_alert_html(alert, 'medium')
        
        html += "</body></html>"
        return html
    
    def _format_alert_html(self, alert: Dict, severity_class: str) -> str:
        """Format single alert as HTML"""
        action_items = "<ul>"
        for item in alert.get('action_items', []):
            action_items += f"<li>{item}</li>"
        action_items += "</ul>"
        
        return f"""
        <div class="alert-box {severity_class}">
          <h3>{alert['message']}</h3>
          <p><strong>Entity:</strong> {alert['entity_type']} - {alert['entity_id']}</p>
          <p><strong>Action Items:</strong></p>
          {action_items}
        </div>
        """

def run_alerts():
    """Cloud Run job entry point"""
    engine = AlertEngine()
    results = engine.run_all_checks()
    
    # Send notifications for critical/high alerts
    critical_high = [a for a in results['alerts'] 
                     if a['severity'] in ['CRITICAL', 'HIGH']]
    
    if critical_high:
        sender = NotificationSender()
        # sender.send_email_alert(critical_high, "your-email@example.com")

if __name__ == "__main__":
    run_alerts()

import boto3
import os
from typing import List

ses = boto3.client('ses', region_name=os.getenv('AWS_REGION', 'ap-south-1'))

SENDER = os.getenv('SES_SENDER_EMAIL', 'orders@thecosmicconnect.com')

def send_order_confirmation(
    customer_email: str,
    customer_name: str,
    order_id: str,
    items: List[dict],
    total: float,
    currency: str,
    gateway: str,
):
    symbol = '₹' if currency == 'INR' else '$'

    # Build items HTML
    items_html = ''.join([
        f"""<tr>
          <td style="padding:8px 12px;border-bottom:1px solid #2D1B5E;color:#F5EDD6;font-family:Georgia,serif">
            {item['name']}
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #2D1B5E;color:#F5EDD6;text-align:center">
            ×{item['quantity']}
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #2D1B5E;color:#C9A84C;text-align:right;font-weight:bold">
            {symbol}{item['priceINR'] * item['quantity'] if currency == 'INR' else item['priceUSD'] * item['quantity']:.2f}
          </td>
        </tr>"""
        for item in items
    ])

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Order Confirmation</title></head>
    <body style="margin:0;padding:0;background:#0A0708;font-family:Arial,sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td align="center" style="padding:40px 20px">
            <table width="600" cellpadding="0" cellspacing="0"
              style="background:#1A0A2E;border:1px solid #C9A84C33;max-width:600px;width:100%">

              <!-- Header -->
              <tr>
                <td style="background:linear-gradient(135deg,#1A0A2E,#2D1B5E);
                  padding:32px;text-align:center;border-bottom:1px solid #C9A84C44">
                  <p style="color:#C9A84C;font-size:11px;letter-spacing:4px;
                    text-transform:uppercase;margin:0 0 8px">✦ The Cosmic Connect ✦</p>
                  <h1 style="color:#F5EDD6;font-size:24px;margin:0;font-weight:normal">
                    Order Confirmed!
                  </h1>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:32px">
                  <p style="color:#F5EDD6;font-family:Georgia,serif;font-size:18px;
                    font-style:italic;margin:0 0 20px">
                    Dear {customer_name},
                  </p>
                  <p style="color:#F5EDD6aa;font-size:14px;line-height:1.7;margin:0 0 24px">
                    Thank you for your order! Your healing crystals are being carefully
                    prepared and energized by our Reiki Grand Masters before dispatch.
                  </p>

                  <!-- Order ID -->
                  <div style="background:#0A070888;border:1px solid #C9A84C33;
                    padding:16px;margin-bottom:24px;text-align:center">
                    <p style="color:#C9A84C88;font-size:11px;letter-spacing:3px;
                      text-transform:uppercase;margin:0 0 4px">Order ID</p>
                    <p style="color:#C9A84C;font-weight:bold;font-size:14px;
                      letter-spacing:2px;margin:0">{order_id}</p>
                    <p style="color:#F5EDD655;font-size:12px;margin:4px 0 0;
                      text-transform:capitalize">via {gateway}</p>
                  </div>

                  <!-- Items table -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                    style="border:1px solid #2D1B5E;margin-bottom:24px">
                    <tr style="background:#2D1B5E66">
                      <th style="padding:10px 12px;color:#C9A84C;font-size:11px;
                        letter-spacing:2px;text-align:left;text-transform:uppercase">Item</th>
                      <th style="padding:10px 12px;color:#C9A84C;font-size:11px;
                        letter-spacing:2px;text-align:center;text-transform:uppercase">Qty</th>
                      <th style="padding:10px 12px;color:#C9A84C;font-size:11px;
                        letter-spacing:2px;text-align:right;text-transform:uppercase">Price</th>
                    </tr>
                    {items_html}
                    <tr>
                      <td colspan="2" style="padding:12px;color:#F5EDD6;font-weight:bold;text-align:right">
                        Total
                      </td>
                      <td style="padding:12px;color:#C9A84C;font-weight:bold;text-align:right;font-size:16px">
                        {symbol}{total:.2f if currency == 'USD' else f'{int(total):,}'}
                      </td>
                    </tr>
                  </table>

                  <p style="color:#F5EDD666;font-size:13px;line-height:1.7;margin:0 0 8px">
                    We will send you a shipping confirmation with tracking details once your
                    order is dispatched. For any queries, contact us at:
                  </p>
                  <p style="margin:0">
                    <a href="mailto:info@thecosmicconnect.com"
                      style="color:#C9A84C;font-size:13px">info@thecosmicconnect.com</a>
                    &nbsp;·&nbsp;
                    <a href="tel:+919599474758" style="color:#C9A84C;font-size:13px">+91 95994 74758</a>
                  </p>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="padding:24px;border-top:1px solid #C9A84C22;text-align:center">
                  <p style="color:#F5EDD633;font-size:11px;margin:0">
                    © The Cosmic Connect · GG1/5A PVR Road, Vikaspuri, New Delhi 110018
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    ses.send_email(
        Source=SENDER,
        Destination={'ToAddresses': [customer_email]},
        Message={
            'Subject': {'Data': f'Order Confirmed — The Cosmic Connect (#{order_id[:8].upper()})'},
            'Body': {'Html': {'Data': html_body}},
        },
    )

    # Also notify the store owner
    try:
        owner_email = os.getenv('OWNER_EMAIL', 'info@thecosmicconnect.com')
        ses.send_email(
            Source=SENDER,
            Destination={'ToAddresses': [owner_email]},
            Message={
                'Subject': {'Data': f'New Order #{order_id[:8].upper()} — {symbol}{total}'},
                'Body': {'Html': {'Data': html_body}},
            },
        )
    except Exception:
        pass  # Don't fail the order if owner notification fails

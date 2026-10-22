#!/usr/bin/env python3
"""Branded Custom Liquid blocks for the Shopify Messaging automations.

Usage:  python3 notifications/marketing/build_blocks.py

Shopify's own product and button blocks stay in each email (they hold the link
back to the cart or checkout); these blocks add the branded hero, the message in
English and Arabic, the trust badges and the WhatsApp strip. Email-safe: tables
and inline styles only. Also writes preview.html to check the look in a browser.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent
INK, YELLOW, CREAM, MUTED, LINE = "#0A0A0A", "#FEBD19", "#FFF6DD", "#71717A", "#E4E4E7"
EN = "'Poppins', Arial, Helvetica, sans-serif"
AR = "'Cairo', Tahoma, Arial, sans-serif"
WA = "https://wa.me/201028305495"
NAME = '{{ customer.first_name | default: "there" }}'
NAME_AR = "{{ customer.first_name }}"

EMAILS = {
    "browse_abandonment_block": {
        "kicker": ("STILL AVAILABLE", "لسه متاح"),
        "title": ("Still thinking <span style=\"color:%s;\">about it?</span>" % YELLOW,
                  "لسه بتفكر <span style=\"color:%s;\">فيه؟</span>" % YELLOW),
        "lead": ("Hi %s, the item you viewed is still in stock, but quantities are limited." % NAME,
                 "أهلاً %s، المنتج اللي شفته لسه موجود، بس الكمية محدودة." % NAME_AR),
    },
    "abandoned_cart_block": {
        "kicker": ("YOUR CART IS SAVED", "سلتك محفوظة"),
        "title": ("Your gear is <span style=\"color:%s;\">waiting.</span>" % YELLOW,
                  "حاجتك <span style=\"color:%s;\">مستنياك.</span>" % YELLOW),
        "lead": ("Hi %s, we kept your items for you. They're not reserved until you order, so don't miss out." % NAME,
                 "أهلاً %s، حفظنالك المنتجات، بس مش بتتحجز غير لما تطلب، فمتفوتهاش." % NAME_AR),
    },
    "abandoned_checkout_block": {
        "kicker": ("ONE STEP LEFT", "فاضل خطوة"),
        "title": ("Your order is <span style=\"color:%s;\">almost done.</span>" % YELLOW,
                  "طلبك <span style=\"color:%s;\">قرب يخلص.</span>" % YELLOW),
        "lead": ("Hi %s, your details are saved. Finish in a minute and pay when it arrives, no card needed." % NAME,
                 "أهلاً %s، بياناتك محفوظة. كمّل في دقيقة وادفع لما الطلب يوصلك، من غير كارت." % NAME_AR),
    },
}

BADGES = [("💵", "Cash on delivery", "الدفع عند الاستلام"),
          ("🚚", "All governorates", "توصيل لكل المحافظات"),
          ("↩️", "7-day returns", "استرجاع خلال 7 أيام")]


def hero(e):
    k_en, k_ar = e["kicker"]
    t_en, t_ar = e["title"]
    l_en, l_ar = e["lead"]
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{INK};border-radius:24px;">
  <tr><td style="padding:32px 28px 28px;">
    <span style="display:inline-block;background:{YELLOW};color:{INK};font-family:{EN};font-size:11px;font-weight:700;letter-spacing:1.5px;padding:6px 12px;border-radius:999px;">{k_en} &nbsp;·&nbsp; <span style="font-family:{AR};letter-spacing:0;">{k_ar}</span></span>
    <h1 style="margin:18px 0 10px;font-family:{EN};font-size:32px;line-height:1.1;font-weight:800;letter-spacing:-0.5px;color:#FFFFFF;">{t_en}</h1>
    <p style="margin:0 0 22px;font-family:{EN};font-size:15px;line-height:1.6;color:#D4D4D8;">{l_en}</p>
    <div dir="rtl" style="border-top:1px solid #27272A;padding-top:20px;text-align:right;">
      <h2 style="margin:0 0 8px;font-family:{AR};font-size:28px;line-height:1.3;font-weight:800;color:#FFFFFF;">{t_ar}</h2>
      <p style="margin:0;font-family:{AR};font-size:15px;line-height:1.8;color:#D4D4D8;">{l_ar}</p>
    </div>
  </td></tr>
</table>"""


def badges():
    cells = "".join(
        f"""<td width="33%" valign="top" style="padding:0 4px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{CREAM};border-radius:16px;">
        <tr><td align="center" style="padding:16px 8px;">
          <div style="font-size:22px;line-height:1;">{icon}</div>
          <div style="margin-top:8px;font-family:{EN};font-size:12px;font-weight:700;color:{INK};">{en}</div>
          <div style="margin-top:2px;font-family:{AR};font-size:12px;font-weight:600;color:{INK};" dir="rtl">{ar}</div>
        </td></tr>
      </table>
    </td>""" for icon, en, ar in BADGES)
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;">
  <tr>{cells}</tr>
</table>"""


def whatsapp():
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;border:1px solid {LINE};border-radius:16px;">
  <tr><td align="center" style="padding:16px;">
    <p style="margin:0;font-family:{EN};font-size:13px;color:{MUTED};">Questions? We reply fast on WhatsApp</p>
    <p style="margin:2px 0 0;font-family:{AR};font-size:13px;color:{MUTED};" dir="rtl">عندك سؤال؟ كلمنا واتساب وهنرد بسرعة</p>
    <a href="{WA}" style="display:inline-block;margin-top:10px;background:#25D366;color:#FFFFFF;font-family:{EN};font-size:14px;font-weight:700;text-decoration:none;padding:10px 20px;border-radius:999px;">WhatsApp +20 102 830 5495</a>
    <p style="margin:10px 0 0;font-family:{EN},{AR};font-size:12px;color:{MUTED};">5 branches in Cairo &amp; Giza &nbsp;|&nbsp; 5 فروع في القاهرة والجيزة</p>
  </td></tr>
</table>"""


def block(e):
    return "\n".join([hero(e), badges(), whatsapp()]) + "\n"


def main():
    preview = []
    for name, e in EMAILS.items():
        html = block(e)
        (OUT / f"{name}.liquid").write_text(html, encoding="utf-8")
        # preview: Liquid name tags shown as a sample name
        sample = html.replace(NAME, "Mina").replace(NAME_AR, "مينا")
        preview.append(f'<h3 style="font-family:Arial;color:#71717A;">{name}</h3>'
                       f'<div style="max-width:600px;background:#fff;padding:16px;margin-bottom:40px;">{sample}'
                       f'<div style="margin-top:16px;text-align:center;"><span style="display:inline-block;background:{YELLOW};color:{INK};'
                       f'font-family:{EN};font-weight:700;padding:14px 32px;border-radius:999px;">(Shopify button) Complete your order</span></div></div>')
    (OUT / "preview.html").write_text(
        '<!doctype html><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Poppins:wght@400;700;800&display=swap" rel="stylesheet">'
        '<body style="background:#F4F4F5;padding:24px;">' + "".join(preview) + "</body>", encoding="utf-8")
    print("wrote", ", ".join(EMAILS), "+ preview.html")


if __name__ == "__main__":
    main()

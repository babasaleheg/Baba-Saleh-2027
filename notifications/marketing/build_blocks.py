#!/usr/bin/env python3
"""Branded Custom Liquid blocks for the Shopify Messaging automations.

Usage:  python3 notifications/marketing/build_blocks.py

No emojis (they render differently per phone); Arabic text uses Arabic digits.

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
NAME_AR = '<span style="direction:ltr;unicode-bidi:embed;">{{ customer.first_name }}</span>'

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

BADGES = [("Cash on delivery", "الدفع عند الاستلام"),
          ("Delivery to all governorates", "توصيل لكل المحافظات"),
          ("7-day returns", "استرجاع خلال ٧ أيام")]

# Shopify's email editor drops dir="rtl", so Arabic direction is set in the style itself too.
RTL = "direction:rtl;unicode-bidi:embed;text-align:right;"
LTR_ISO = "direction:ltr;unicode-bidi:embed;"


def hero(e):
    k_en, k_ar = e["kicker"]
    t_en, t_ar = e["title"]
    l_en, l_ar = e["lead"]
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{INK};border-radius:20px;">
  <tr><td style="padding:36px 32px 32px;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="background:{YELLOW};border-radius:999px;padding:6px 14px;font-family:{EN};font-size:11px;font-weight:700;letter-spacing:2px;color:{INK};">{k_en}</td>
    </tr></table>
    <h1 style="margin:20px 0 12px;font-family:{EN};font-size:30px;line-height:1.15;font-weight:800;letter-spacing:-0.5px;color:#FFFFFF;">{t_en}</h1>
    <p style="margin:0;font-family:{EN};font-size:15px;line-height:1.65;color:#A1A1AA;">{l_en}</p>
    <div style="height:1px;background:#27272A;margin:28px 0;line-height:1px;font-size:1px;">&nbsp;</div>
    <div dir="rtl" style="{RTL}">
      <h2 dir="rtl" style="{RTL}margin:0 0 10px;font-family:{AR};font-size:26px;line-height:1.4;font-weight:800;color:#FFFFFF;">{t_ar}</h2>
      <p dir="rtl" style="{RTL}margin:0;font-family:{AR};font-size:15px;line-height:1.9;color:#A1A1AA;">{l_ar}</p>
    </div>
  </td></tr>
</table>"""


def badges():
    cells = []
    for i, (en, ar) in enumerate(BADGES):
        sep = "" if i == 0 else f"border-left:1px solid {LINE};"
        cells.append(f"""<td width="33%" valign="top" align="center" style="padding:18px 10px;{sep}">
      <div style="width:24px;height:3px;background:{YELLOW};border-radius:2px;margin:0 auto 10px;line-height:3px;font-size:1px;">&nbsp;</div>
      <div style="font-family:{EN};font-size:13px;line-height:1.4;font-weight:700;color:{INK};">{en}</div>
      <div dir="rtl" style="direction:rtl;unicode-bidi:embed;margin-top:4px;font-family:{AR};font-size:13px;line-height:1.6;color:{MUTED};">{ar}</div>
    </td>""")
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;border:1px solid {LINE};border-radius:16px;">
  <tr>{"".join(cells)}</tr>
</table>"""


def whatsapp():
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
  <tr><td align="center" style="padding:8px 16px 4px;">
    <p style="margin:0;font-family:{EN};font-size:14px;line-height:1.6;color:{INK};font-weight:600;">Questions? Chat with us on WhatsApp</p>
    <p dir="rtl" style="direction:rtl;unicode-bidi:embed;margin:2px 0 14px;font-family:{AR};font-size:14px;line-height:1.7;color:{INK};font-weight:600;">عندك سؤال؟ كلمنا على واتساب</p>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="background:{INK};border-radius:999px;">
        <a href="{WA}" style="display:inline-block;padding:12px 26px;font-family:{EN};font-size:14px;font-weight:700;color:{YELLOW};text-decoration:none;{LTR_ISO}">+20 102 830 5495</a>
      </td>
    </tr></table>
    <p style="margin:16px 0 0;font-family:{EN};font-size:12px;line-height:1.6;color:{MUTED};">Baba Saleh Sports &middot; 5 branches in Cairo &amp; Giza</p>
    <p dir="rtl" style="direction:rtl;unicode-bidi:embed;margin:0;font-family:{AR};font-size:12px;line-height:1.7;color:{MUTED};">بابا صالح للرياضة &middot; ٥ فروع في القاهرة والجيزة</p>
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
        # simulate Shopify's editor, which strips dir=: the styles alone must keep Arabic right
        import re
        sample = re.sub(r' dir="(rtl|ltr)"', "", html.replace("{{ customer.first_name | default: \"there\" }}", "Bob").replace("{{ customer.first_name }}", "Bob"))
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

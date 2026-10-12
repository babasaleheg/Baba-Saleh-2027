#!/usr/bin/env python3
"""Generate Baba Saleh Shopify notification templates (EN + AR) and README.

Usage:  python3 notifications/build.py

Brand settings, the shared layout (header / help box / footer) and every
notification body live here.  Edit this file, re-run it, and paste the
regenerated .liquid files into Shopify admin.  Stdlib only.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Brand
# --------------------------------------------------------------------------
INK, BLUE, YELLOW, RED = "#0A0A0A", "#1E3AFF", "#FEBD19", "#E5242B"
SURFACE, MUTED, LINE, WHITE = "#F4F4F5", "#6B7280", "#E4E4E7", "#FFFFFF"
LOGO = "https://babasaleh.myshopify.com/cdn/shop/files/baba-saleh-logo-desktop.png"
SITE = "https://babasaleh.com"
WA_LINK, WA_TEXT = "https://wa.me/201028305495", "+20 102 830 5495"
EMAIL = "support@babasaleh.com"
ADMIN = "https://admin.shopify.com/store/x1hnz9-tu"
FONTS_LINK = ("https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700"
              "&family=Poppins:wght@400;600;700&display=swap")
FONT = {
    "en": "'Poppins', Arial, Helvetica, sans-serif",
    "ar": "'Cairo', Tahoma, Arial, sans-serif",
}

# Current language while rendering (set by build()).
LANG = "en"


def t(en, ar):
    """Pick the string for the language being rendered."""
    return en if LANG == "en" else ar


def start():
    return "left" if LANG == "en" else "right"


def end():
    return "right" if LANG == "en" else "left"


def ff():
    return FONT[LANG]


def money(expr):
    """Money output, isolated LTR so 'EGP 1,200' never flips inside RTL text."""
    return '<span dir="ltr">{{ %s | money }}</span>' % expr


# --------------------------------------------------------------------------
# Small building blocks
# --------------------------------------------------------------------------
def h1(text):
    return (f'<h1 class="h1 t-ink" style="margin:0 0 12px;font-family:{ff()};font-size:26px;'
            f'line-height:1.3;font-weight:700;color:{INK};">{text}</h1>\n')


def h2(text):
    return (f'<h2 class="t-ink" style="margin:28px 0 8px;font-family:{ff()};font-size:17px;'
            f'line-height:1.4;font-weight:700;color:{INK};">{text}</h2>\n')


def p(text, muted=False, size=15):
    cls, col = ("t-muted", MUTED) if muted else ("t-ink", INK)
    return (f'<p class="{cls}" style="margin:0 0 14px;font-family:{ff()};font-size:{size}px;'
            f'line-height:1.65;color:{col};">{text}</p>\n')


def greeting(var="customer.first_name"):
    return p(t(f"{{% if {var} != blank %}}Hi {{{{ {var} }}}},{{% else %}}Hi there,{{% endif %}}",
               f"{{% if {var} != blank %}}أهلاً {{{{ {var} }}}}،{{% else %}}أهلاً بك،{{% endif %}}"))


def button(href, label, bg=BLUE, fg=WHITE):
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" border="0" class="btn" style="margin:22px 0 8px;">
  <tr><td align="center" bgcolor="{bg}" style="border-radius:10px;background:{bg};">
    <a href="{href}" target="_blank" style="display:inline-block;padding:14px 30px;font-family:{ff()};font-size:16px;font-weight:700;line-height:1.2;color:{fg};text-decoration:none;border-radius:10px;">{label}</a>
  </td></tr>
</table>
"""


def box(inner, bg=SURFACE, border=None):
    """Tinted callout box. border = colour of the start-side accent bar."""
    side = "left" if LANG == "en" else "right"
    accent = f"border-{side}:4px solid {border};" if border else ""
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0;">
  <tr><td class="surface" bgcolor="{bg}" style="background:{bg};{accent}border-radius:10px;padding:16px 18px;font-family:{ff()};font-size:14px;line-height:1.6;color:{INK};" align="{start()}">
{inner}
  </td></tr>
</table>
"""


def kv_rows(rows):
    """Two-column label/value table. rows = [(label, value_html, liquid_condition_or_None)]."""
    out = ['<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0;">']
    for label, value, cond in rows:
        row = (f'<tr><td class="t-muted" style="padding:5px 0;font-family:{ff()};font-size:14px;color:{MUTED};" align="{start()}">{label}</td>'
               f'<td class="t-ink" style="padding:5px 0;font-family:{ff()};font-size:14px;color:{INK};font-weight:600;" align="{end()}">{value}</td></tr>')
        out.append(f"{{% if {cond} %}}{row}{{% endif %}}" if cond else row)
    out.append("</table>\n")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Order building blocks
# --------------------------------------------------------------------------
def order_meta(include_payment=True):
    rows = [
        (t("Order number", "رقم الطلب"), '<span dir="ltr">{{ name }}</span>', None),
        (t("Order date", "تاريخ الطلب"), '<span dir="ltr">{{ created_at | date: "%d/%m/%Y" }}</span>', "created_at"),
    ]
    if include_payment:
        rows.append((t("Payment", "طريقة الدفع"), "{{ bs_gateway }}", "bs_gateway != blank"))
    return ("{% assign bs_gateway = transactions.first.gateway_display_name | default: gateway %}\n"
            if include_payment else "") + kv_rows(rows)


def _thumb(obj):
    return (f'{{% if {obj}.image %}}<img src="{{{{ {obj} | img_url: \'compact_cropped\' }}}}" alt="{{{{ bs_title | escape }}}}" '
            f'width="56" height="56" class="thumb" style="display:block;width:56px;height:56px;border-radius:8px;border:1px solid {LINE};object-fit:cover;">{{% endif %}}')


def line_items(source="subtotal_line_items", kind="order"):
    """Line-item table.

    kind: order    -> loop items directly, show price
          checkout -> same as order (abandoned checkout line items)
          fulfill  -> loop fulfillment_line_items (item in .line_item), no price
          refund   -> loop refund_line_items (item in .line_item), no price
    """
    wrapped = kind in ("fulfill", "refund")
    loop_var = "bs_row" if wrapped else "line"
    open_loop = f"{{% for {loop_var} in {source} %}}"
    if wrapped:
        open_loop += "{% assign line = bs_row.line_item %}{% assign bs_qty = bs_row.quantity %}"
    else:
        open_loop += "{% assign bs_qty = line.quantity %}"
    open_loop += ("{% if line.product.title != blank %}{% assign bs_title = line.product.title %}"
                  "{% else %}{% assign bs_title = line.title %}{% endif %}")
    price = ""
    if not wrapped:
        price = (f'<td class="line t-ink" valign="top" align="{end()}" style="padding:12px 0;border-bottom:1px solid {LINE};'
                 f'font-family:{ff()};font-size:14px;font-weight:600;color:{INK};white-space:nowrap;">'
                 + money("line.final_line_price")
                 + "{% if line.original_line_price > line.final_line_price %}<br>"
                 f'<s class="t-muted" style="font-weight:400;color:{MUTED};">' + money("line.original_line_price") + "</s>{% endif %}</td>")
    variant = ("{% if line.variant.title != blank and line.variant.title != 'Default Title' %}"
               f'<div class="t-muted" style="font-size:13px;color:{MUTED};">{{{{ line.variant.title }}}}</div>{{% endif %}}')
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:6px 0 4px;border-top:1px solid {LINE};" class="line">
{open_loop}
<tr>
  <td class="line" width="68" valign="top" style="padding:12px 0;border-bottom:1px solid {LINE};width:68px;">{_thumb('line')}</td>
  <td class="line" valign="top" align="{start()}" style="padding:12px 10px;border-bottom:1px solid {LINE};font-family:{ff()};font-size:14px;line-height:1.5;">
    <div class="t-ink" style="font-weight:600;color:{INK};">{{{{ bs_title }}}}</div>
    {variant}
    <div class="t-muted" style="font-size:13px;color:{MUTED};">{t('Qty', 'الكمية')}: <span dir="ltr">{{{{ bs_qty }}}}</span></div>
  </td>
  {price}
</tr>
{{% endfor %}}
</table>
"""


def totals(with_cod=True):
    rows = [
        (t("Subtotal", "المجموع الفرعي"), money("subtotal_price"), None),
        (t("Discount", "الخصم"), f'<span dir="ltr" style="color:{RED};">-{{{{ total_discounts | money }}}}</span>', "total_discounts > 0"),
        (t("Shipping", "الشحن"),
         "{% if shipping_price == 0 %}" + t("Free", "مجاني") + "{% else %}" + money("shipping_price") + "{% endif %}",
         "shipping_price != nil"),
        (t("Taxes", "الضرائب"), money("tax_price"), "tax_price > 0"),
    ]
    html = kv_rows(rows)
    html += (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:2px solid {INK};" class="line">'
             f'<tr><td class="t-ink" style="padding:10px 0;font-family:{ff()};font-size:16px;font-weight:700;color:{INK};" align="{start()}">{t("Total", "الإجمالي")}</td>'
             f'<td class="t-ink" style="padding:10px 0;font-family:{ff()};font-size:18px;font-weight:700;color:{INK};" align="{end()}">{money("total_price")}</td></tr></table>\n')
    if with_cod:
        html += cod_box()
    return html


def cod_box():
    """Shown while the order still has an amount due (cash on delivery)."""
    return ("{% assign bs_due = total_outstanding | default: total_price %}"
            "{% unless financial_status == 'paid' or financial_status == 'refunded' or financial_status == 'voided' or bs_due == 0 %}\n"
            + box(t("<strong>Cash on delivery</strong><br>Please have " + money("bs_due")
                    + " ready when our courier arrives. Card payments may be available on delivery too.",
                    "<strong>الدفع عند الاستلام</strong><br>يُرجى تجهيز مبلغ " + money("bs_due")
                    + " عند وصول المندوب. قد يتوفر الدفع بالبطاقة عند الاستلام أيضاً."),
                  bg="#FFF6DD", border=YELLOW)
            + "{% endunless %}\n")


def address(var, title):
    return (f"{{% if {var} %}}\n" + h2(title)
            + p(f"{{{{ {var}.name }}}}<br>{{{{ {var}.address1 }}}}"
                f"{{% if {var}.address2 != blank %}}<br>{{{{ {var}.address2 }}}}{{% endif %}}"
                f"<br>{{{{ {var}.city }}}}{{% if {var}.province != blank %}}, {{{{ {var}.province }}}}{{% endif %}}"
                f"<br>{{{{ {var}.country }}}}"
                f"{{% if {var}.phone != blank %}}<br><span dir=\"ltr\">{{{{ {var}.phone }}}}</span>{{% endif %}}", size=14)
            + "{% endif %}\n")


def shipping_block():
    return (address("shipping_address", t("Delivery address", "عنوان التوصيل"))
            + "{% if shipping_method.title != blank %}"
            + p(f'<span class="t-muted" style="color:{MUTED};">{t("Shipping method", "طريقة الشحن")}:</span> {{{{ shipping_method.title }}}}', size=14)
            + "{% endif %}\n")


def tracking_block():
    track = t("Track shipment", "تتبّع الشحنة")
    return ("{% if fulfillment.tracking_numbers.size > 0 %}\n" + box(
        "{% if fulfillment.tracking_company != blank %}"
        f'<div><span class="t-muted" style="color:{MUTED};">{t("Courier", "شركة الشحن")}:</span> <strong>{{{{ fulfillment.tracking_company }}}}</strong></div>{{% endif %}}\n'
        "{% for bs_tn in fulfillment.tracking_numbers %}{% assign bs_tu = fulfillment.tracking_urls[forloop.index0] %}"
        f'<div style="margin-top:6px;"><span class="t-muted" style="color:{MUTED};">{t("Tracking number", "رقم التتبع")}:</span> '
        '<strong dir="ltr">{{ bs_tn }}</strong>'
        f'{{% if bs_tu != blank %}} &nbsp;<a class="t-link" href="{{{{ bs_tu }}}}" style="color:{BLUE};font-weight:700;">{track}</a>{{% endif %}}</div>'
        "{% endfor %}") + "{% endif %}\n")


def returns_note():
    return box(t("<strong>7-day returns.</strong> Changed your mind or need another size? You can return or exchange within 7 days of delivery. "
                 f'Just message us on <a class="t-link" href="{WA_LINK}" style="color:{BLUE};">WhatsApp</a>.',
                 "<strong>استرجاع خلال 7 أيام.</strong> غيّرت رأيك أو تحتاج مقاساً آخر؟ يمكنك الاسترجاع أو الاستبدال خلال 7 أيام من الاستلام. "
                 f'فقط راسلنا على <a class="t-link" href="{WA_LINK}" style="color:{BLUE};">واتساب</a>.'))


def status_button():
    return "{% if order_status_url != blank %}" + button("{{ order_status_url }}", t("View order status", "تابع حالة طلبك")) + "{% endif %}\n"


# --------------------------------------------------------------------------
# Layout (shared header / help box / footer)
# --------------------------------------------------------------------------
def page(title, preheader, body, staff=False):
    """body is HTML for the current LANG, or a list of (lang, html) parts rendered one after another."""
    global LANG
    parts = body if isinstance(body, list) else [(LANG, body)]
    rows, trust_lines, stores, wa = [], [], [], []
    for i, (LANG, part) in enumerate(parts):
        rows.append(section(part, staff, divider=i > 0))
        trust_lines.append(t("Cash on delivery &nbsp;·&nbsp; Shipping to all governorates &nbsp;·&nbsp; 7-day returns",
                             "الدفع عند الاستلام &nbsp;·&nbsp; شحن لجميع المحافظات &nbsp;·&nbsp; استرجاع خلال 7 أيام"))
        stores.append(t("Baba Saleh Sports Egypt", "بابا صالح للأدوات الرياضية - مصر"))
        wa.append(t("WhatsApp", "واتساب"))
    LANG = parts[0][0]
    return shell(title, preheader, "\n".join(rows), "<br>".join(trust_lines),
                 " &nbsp;·&nbsp; ".join(stores), " / ".join(wa), staff)


def section(body, staff, divider=False):
    """One language block (body card + help box), aligned for the current LANG."""
    direction = "ltr" if LANG == "en" else "rtl"
    sep = f"""
<tr><td class="card px" bgcolor="{WHITE}" style="background:{WHITE};padding:8px 32px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td class="line" style="border-top:2px dashed #E4E4E7;font-size:0;line-height:0;height:1px;">&nbsp;</td>
  </tr></table>
</td></tr>""" if divider else ""
    help_box = "" if staff else f"""
<tr><td class="card px" bgcolor="{WHITE}" style="background:{WHITE};padding:0 32px 28px;" align="{start()}">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td class="surface" bgcolor="{SURFACE}" style="background:{SURFACE};border-radius:12px;padding:18px;font-family:{ff()};font-size:14px;line-height:1.6;color:{INK};" align="{start()}">
      <strong class="t-ink" style="color:{INK};">{t("Need help?", "تحتاج مساعدة؟")}</strong><br>
      <span class="t-muted" style="color:{MUTED};">{t("Our team replies fastest on WhatsApp.", "فريقنا يرد بشكل أسرع على واتساب.")}</span><br>
      <a class="t-link" href="{WA_LINK}" style="color:{BLUE};font-weight:700;text-decoration:none;">{t("WhatsApp", "واتساب")} <span dir="ltr">{WA_TEXT}</span></a>
      &nbsp;·&nbsp; <a class="t-link" href="mailto:{EMAIL}" style="color:{BLUE};text-decoration:none;">{EMAIL}</a>
    </td></tr>
  </table>
</td></tr>"""
    return f"""{sep}
<!-- Body ({LANG}) -->
<tr><td class="card px" bgcolor="{WHITE}" dir="{direction}" lang="{LANG}" style="background:{WHITE};padding:32px 32px 12px;font-family:{ff()};" align="{start()}">
{body}
</td></tr>
{help_box}"""


def shell(title, preheader, bodies, trust, store, wa_label, staff):
    lang, direction = LANG, ("ltr" if LANG == "en" else "rtl")
    return f"""{{% comment %}} Baba Saleh notification template. Generated by notifications/build.py - edit the generator, not this file. {{% endcomment %}}
<!DOCTYPE html>
<html lang="{lang}" dir="{direction}" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{title}</title>
<link href="{FONTS_LINK}" rel="stylesheet">
<style>
  body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
  table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; border-collapse:collapse; }}
  img {{ border:0; outline:none; text-decoration:none; -ms-interpolation-mode:bicubic; }}
  body {{ margin:0 !important; padding:0 !important; width:100% !important; background:{SURFACE}; font-family:{ff()}; }}
  a {{ color:{BLUE}; }}
  .t-link:hover {{ text-decoration:underline !important; }}
  @media only screen and (max-width:620px) {{
    .container {{ width:100% !important; }}
    .px {{ padding-left:16px !important; padding-right:16px !important; }}
    .h1 {{ font-size:22px !important; }}
    .btn, .btn td, .btn a {{ display:block !important; width:100% !important; box-sizing:border-box; text-align:center !important; }}
    .thumb {{ width:48px !important; height:48px !important; }}
  }}
  /* Dark mode: explicit dark surfaces; header band is already ink and the logo sits on a white chip. */
  @media (prefers-color-scheme: dark) {{
    body, .wrap {{ background:#000000 !important; }}
    .card {{ background:#18181B !important; }}
    .surface {{ background:#27272A !important; }}
    .t-ink {{ color:#F4F4F5 !important; }}
    .t-muted {{ color:#A1A1AA !important; }}
    .t-link {{ color:#9DABFF !important; }}
    .line {{ border-color:#3F3F46 !important; }}
  }}
  [data-ogsc] .t-ink {{ color:#F4F4F5 !important; }}
  [data-ogsc] .t-muted {{ color:#A1A1AA !important; }}
  [data-ogsc] .t-link {{ color:#9DABFF !important; }}
  [data-ogsb] .card {{ background:#18181B !important; }}
  [data-ogsb] .surface {{ background:#27272A !important; }}
</style>
</head>
<body class="wrap" dir="{direction}" style="margin:0;padding:0;background:{SURFACE};">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:{SURFACE};opacity:0;">{preheader}&#8199;&#65279;&#847;&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>
<table role="presentation" class="wrap" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{SURFACE}" style="background:{SURFACE};">
<tr><td align="center" style="padding:24px 10px;">
<table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;" dir="{direction}">

<!-- Header -->
<tr><td height="6" bgcolor="{YELLOW}" style="background:{YELLOW};height:6px;line-height:6px;font-size:0;border-radius:14px 14px 0 0;">&nbsp;</td></tr>
<tr><td bgcolor="{INK}" align="center" style="background:{INK};padding:22px 24px;">
  <a href="{SITE}" target="_blank" style="text-decoration:none;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td bgcolor="{WHITE}" style="background:{WHITE};border-radius:10px;padding:10px 16px;">
        <img src="{LOGO}" width="180" alt="Baba Saleh" style="display:block;width:180px;max-width:100%;height:auto;border:0;font-family:Arial,sans-serif;font-size:20px;font-weight:700;color:{INK};">
      </td>
    </tr></table>
  </a>
</td></tr>

{bodies}

<!-- Footer -->
<tr><td bgcolor="{INK}" align="center" style="background:{INK};padding:22px 24px;border-radius:0 0 14px 14px;font-family:{ff()};font-size:13px;line-height:1.7;color:#D4D4D8;">
  <div style="color:{YELLOW};font-weight:700;">{trust}</div>
  <div style="margin-top:8px;">
    <a href="{SITE}" style="color:#FFFFFF;text-decoration:none;">babasaleh.com</a> &nbsp;·&nbsp;
    <a href="{WA_LINK}" style="color:#FFFFFF;text-decoration:none;">{wa_label} <span dir="ltr">{WA_TEXT}</span></a> &nbsp;·&nbsp;
    <a href="mailto:{EMAIL}" style="color:#FFFFFF;text-decoration:none;">{EMAIL}</a>
  </div>
  <div style="margin-top:8px;color:#A1A1AA;">&copy; {{{{ 'now' | date: '%Y' }}}} {store}</div>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Notification bodies.  Each returns (title, preheader, body_html).
# --------------------------------------------------------------------------
def order_confirmation():
    return (t("Order {{ name }} confirmed", "تأكيد الطلب {{ name }}"),
            t("Thanks for shopping with Baba Saleh! Here are your order details.", "شكراً لتسوقك من بابا صالح! إليك تفاصيل طلبك."),
            h1(t("Thank you for your order!", "شكراً لطلبك!")) + greeting()
            + p(t("We've received order <strong dir=\"ltr\">{{ name }}</strong> and our team is getting it ready. We'll let you know as soon as it ships. "
                  "We deliver to every governorate in Egypt.",
                  "استلمنا طلبك رقم <strong dir=\"ltr\">{{ name }}</strong> ويقوم فريقنا بتجهيزه الآن، وسنبلغك فور شحنه. "
                  "نوصّل إلى جميع محافظات مصر."))
            + status_button() + order_meta()
            + h2(t("Order summary", "ملخص الطلب")) + line_items() + totals() + shipping_block())


def order_edited():
    return (t("Order {{ name }} updated", "تم تعديل الطلب {{ name }}"),
            t("Your order has been updated. Review the latest details.", "تم تعديل طلبك. راجع التفاصيل المحدّثة."),
            h1(t("Your order has been updated", "تم تعديل طلبك")) + greeting()
            + p(t("We've made changes to order <strong dir=\"ltr\">{{ name }}</strong>. Here is the updated summary.",
                  "أجرينا تعديلات على طلبك رقم <strong dir=\"ltr\">{{ name }}</strong>. إليك الملخص المحدّث."))
            + status_button() + h2(t("Updated order", "الطلب بعد التعديل")) + line_items() + totals() + shipping_block())


def order_invoice():
    pay = "{% if checkout_payment_collection_url != blank %}{{ checkout_payment_collection_url }}{% else %}{{ order_status_url }}{% endif %}"
    return (t("Payment due for order {{ name }}", "مطلوب سداد الطلب {{ name }}"),
            t("Your order has an outstanding balance.", "يوجد مبلغ مستحق على طلبك."),
            h1(t("Payment needed for your order", "مطلوب سداد قيمة طلبك")) + greeting()
            + p(t("Order <strong dir=\"ltr\">{{ name }}</strong> has an outstanding balance of <strong>" + money("total_outstanding | default: total_price") + "</strong>.",
                  "يوجد على الطلب رقم <strong dir=\"ltr\">{{ name }}</strong> مبلغ مستحق قدره <strong>" + money("total_outstanding | default: total_price") + "</strong>."))
            + "{% if custom_message != blank %}" + box('<div dir="auto">{{ custom_message }}</div>') + "{% endif %}"
            + button(pay, t("Pay now", "ادفع الآن"))
            + h2(t("Order summary", "ملخص الطلب")) + line_items() + totals(with_cod=False))


def draft_order_invoice():
    return (t("Your invoice {{ name }} from Baba Saleh", "فاتورتك {{ name }} من بابا صالح"),
            t("Complete your purchase in one click.", "أكمل طلبك بضغطة واحدة."),
            h1(t("Your invoice is ready", "فاتورتك جاهزة")) + greeting()
            + "{% if custom_message != blank %}" + box('<div dir="auto">{{ custom_message }}</div>') + "{% endif %}"
            + p(t("We've prepared invoice <strong dir=\"ltr\">{{ name }}</strong> for you. Review the items below and complete your order; cash on delivery is available.",
                  "جهّزنا لك الفاتورة رقم <strong dir=\"ltr\">{{ name }}</strong>. راجع المنتجات بالأسفل وأكمل طلبك، والدفع عند الاستلام متاح."))
            + button("{{ invoice_url }}", t("Complete your order", "أكمل طلبك"))
            + "{% if reserve_inventory_until %}" + p(t("Items are reserved for you until ", "المنتجات محجوزة لك حتى ")
                                                      + '<span dir="ltr">{{ reserve_inventory_until | date: "%d/%m/%Y %H:%M" }}</span>.', muted=True, size=13) + "{% endif %}"
            + h2(t("Invoice summary", "ملخص الفاتورة")) + line_items("line_items") + totals(with_cod=False))


def order_canceled():
    reason = ("{% case cancel_reason %}"
              "{% when 'customer' %}" + t("as you requested", "بناءً على طلبك")
              + "{% when 'inventory' %}" + t("because some items are out of stock", "لعدم توفر بعض المنتجات")
              + "{% when 'declined' %}" + t("because the payment was declined", "لرفض عملية الدفع")
              + "{% else %}" + t("by our team", "من قِبل فريقنا") + "{% endcase %}")
    return (t("Order {{ name }} canceled", "تم إلغاء الطلب {{ name }}"),
            t("Your order has been canceled.", "تم إلغاء طلبك."),
            h1(t("Your order has been canceled", "تم إلغاء طلبك")) + greeting()
            + p(t(f"Order <strong dir=\"ltr\">{{{{ name }}}}</strong> was canceled {reason}. You won't be charged for it.",
                  f"تم إلغاء الطلب رقم <strong dir=\"ltr\">{{{{ name }}}}</strong> {reason}. لن يتم تحصيل أي مبلغ مقابله."))
            + "{% if financial_status == 'paid' or financial_status == 'refunded' or financial_status == 'partially_refunded' %}"
            + p(t("If you paid online, your refund goes back to your original payment method. Banks can take 5-10 business days to show it.",
                  "إذا كنت دفعت أونلاين، سيُرد المبلغ إلى وسيلة الدفع الأصلية، وقد يستغرق ظهوره من 5 إلى 10 أيام عمل حسب البنك."), muted=True)
            + "{% endif %}"
            + button(SITE, t("Continue shopping", "تابع التسوق"))
            + h2(t("Canceled items", "المنتجات الملغاة")) + line_items())


def order_refund():
    return (t("Refund for order {{ name }}", "استرداد مبلغ الطلب {{ name }}"),
            t("Your refund has been issued.", "تم إصدار المبلغ المسترد."),
            h1(t("Your refund is on its way", "تم إصدار استرداد المبلغ")) + greeting()
            + "{% if amount %}" + p(t("We've refunded <strong>" + money("amount") + "</strong> for order <strong dir=\"ltr\">{{ name }}</strong>.",
                                     "قمنا برد مبلغ <strong>" + money("amount") + "</strong> عن الطلب رقم <strong dir=\"ltr\">{{ name }}</strong>.")) + "{% else %}"
            + p(t("We've issued a refund for order <strong dir=\"ltr\">{{ name }}</strong>.", "قمنا بإصدار استرداد للطلب رقم <strong dir=\"ltr\">{{ name }}</strong>.")) + "{% endif %}"
            + p(t("Online payments go back to the original payment method (allow 5-10 business days). Cash refunds are arranged with you directly by our team.",
                  "المدفوعات الإلكترونية تُرد إلى وسيلة الدفع الأصلية (خلال 5 إلى 10 أيام عمل)، والمبالغ النقدية يتواصل معك فريقنا لترتيب ردها."), muted=True)
            + "{% if refund_line_items.size > 0 %}" + h2(t("Refunded items", "المنتجات المستردة")) + line_items("refund_line_items", "refund") + "{% endif %}"
            + status_button())


def order_payment_receipt():
    return (t("Payment received for order {{ name }}", "تم استلام الدفع للطلب {{ name }}"),
            t("Thanks, we've received your payment.", "شكراً، استلمنا دفعتك."),
            h1(t("Payment received", "تم استلام الدفع")) + greeting()
            + p(t("We've received your payment" + "{% if transaction.amount %} of <strong>" + money("transaction.amount") + "</strong>{% endif %}"
                  + " for order <strong dir=\"ltr\">{{ name }}</strong>. Thank you!",
                  "استلمنا دفعتك" + "{% if transaction.amount %} بقيمة <strong>" + money("transaction.amount") + "</strong>{% endif %}"
                  + " للطلب رقم <strong dir=\"ltr\">{{ name }}</strong>. شكراً لك!"))
            + kv_rows([(t("Payment method", "طريقة الدفع"), "{{ transaction.gateway_display_name }}", "transaction.gateway_display_name != blank"),
                       (t("Remaining balance", "المبلغ المتبقي"), money("total_outstanding"), "total_outstanding > 0")])
            + status_button())


def shipping_confirmation():
    return (t("Order {{ name }} is on its way", "طلبك {{ name }} في الطريق إليك"),
            t("Good news: your order has shipped.", "خبر سعيد: تم شحن طلبك."),
            h1(t("Your order is on its way!", "طلبك في الطريق إليك!")) + greeting()
            + p(t("Great news: items from order <strong dir=\"ltr\">{{ name }}</strong> have shipped and are heading to you.",
                  "خبر سعيد: تم شحن منتجات طلبك رقم <strong dir=\"ltr\">{{ name }}</strong> وهي في طريقها إليك."))
            + tracking_block() + status_button() + cod_box()
            + h2(t("Items in this shipment", "المنتجات في هذه الشحنة")) + line_items("fulfillment.fulfillment_line_items", "fulfill")
            + address("shipping_address", t("Delivery address", "عنوان التوصيل")))


def shipping_update():
    return (t("Shipping update for order {{ name }}", "تحديث بخصوص شحن الطلب {{ name }}"),
            t("There's an update to your shipment.", "يوجد تحديث على شحنتك."),
            h1(t("Shipping update", "تحديث الشحن")) + greeting()
            + p(t("The shipping details for order <strong dir=\"ltr\">{{ name }}</strong> have been updated. Here is the latest information.",
                  "تم تحديث بيانات شحن طلبك رقم <strong dir=\"ltr\">{{ name }}</strong>. إليك آخر المعلومات."))
            + tracking_block() + status_button()
            + h2(t("Items in this shipment", "المنتجات في هذه الشحنة")) + line_items("fulfillment.fulfillment_line_items", "fulfill"))


def out_for_delivery():
    return (t("Order {{ name }} is out for delivery", "طلبك {{ name }} خرج للتوصيل"),
            t("Your order arrives today. Keep your phone nearby.", "طلبك يصلك اليوم، يُرجى إبقاء هاتفك قريباً."),
            h1(t("Out for delivery today", "طلبك خرج للتوصيل اليوم")) + greeting()
            + p(t("Order <strong dir=\"ltr\">{{ name }}</strong> is out for delivery. Please keep your phone nearby: the courier may call before arriving.",
                  "طلبك رقم <strong dir=\"ltr\">{{ name }}</strong> خرج للتوصيل. يُرجى إبقاء هاتفك قريباً، فقد يتصل بك المندوب قبل الوصول."))
            + cod_box() + tracking_block() + status_button()
            + h2(t("Items in this shipment", "المنتجات في هذه الشحنة")) + line_items("fulfillment.fulfillment_line_items", "fulfill"))


def delivered():
    return (t("Order {{ name }} delivered", "تم توصيل الطلب {{ name }}"),
            t("Your order has arrived. Enjoy your gear!", "وصل طلبك. استمتع بمعداتك!"),
            h1(t("Your order has been delivered", "تم توصيل طلبك")) + greeting()
            + p(t("Order <strong dir=\"ltr\">{{ name }}</strong> has been delivered. We hope you love it! If anything isn't right, tell us and we'll fix it.",
                  "تم توصيل طلبك رقم <strong dir=\"ltr\">{{ name }}</strong>. نتمنى أن ينال إعجابك! وإذا كان هناك أي مشكلة أخبرنا وسنحلها فوراً."))
            + returns_note() + status_button()
            + h2(t("Delivered items", "المنتجات المسلّمة")) + line_items("fulfillment.fulfillment_line_items", "fulfill"))


def ready_for_local_pickup():
    loc = ("{% assign bs_loc = location | default: pickup_location %}{% if bs_loc %}"
           + box(f'<strong>{{{{ bs_loc.name }}}}</strong><br>{{{{ bs_loc.address1 }}}}{{% if bs_loc.address2 != blank %}}, {{{{ bs_loc.address2 }}}}{{% endif %}}<br>{{{{ bs_loc.city }}}}',
                 border=BLUE) + "{% endif %}")
    return (t("Order {{ name }} is ready for pickup", "طلبك {{ name }} جاهز للاستلام"),
            t("Your order is ready to collect.", "طلبك جاهز للاستلام من الفرع."),
            h1(t("Your order is ready for pickup", "طلبك جاهز للاستلام")) + greeting()
            + p(t("Order <strong dir=\"ltr\">{{ name }}</strong> is ready. Bring this email or your order number when you come to collect it.",
                  "طلبك رقم <strong dir=\"ltr\">{{ name }}</strong> جاهز. أحضر هذه الرسالة أو رقم الطلب عند الاستلام."))
            + loc + cod_box() + status_button() + h2(t("Order summary", "ملخص الطلب")) + line_items())


def picked_up_by_customer():
    return (t("Order {{ name }} picked up", "تم استلام الطلب {{ name }}"),
            t("Thanks for picking up your order.", "شكراً لاستلامك طلبك."),
            h1(t("Order picked up", "تم استلام طلبك")) + greeting()
            + p(t("Order <strong dir=\"ltr\">{{ name }}</strong> has been picked up. Thanks for shopping with Baba Saleh!",
                  "تم استلام طلبك رقم <strong dir=\"ltr\">{{ name }}</strong>. شكراً لتسوقك من بابا صالح!"))
            + returns_note() + button(SITE, t("Shop again", "تسوّق مرة أخرى")))


def return_request_confirmation():
    return (t("We received your return request for order {{ name }}", "استلمنا طلب الاسترجاع للطلب {{ name }}"),
            t("We're reviewing your return request.", "نراجع طلب الاسترجاع الآن."),
            h1(t("Return request received", "استلمنا طلب الاسترجاع")) + greeting()
            + p(t("Thanks, we've received your return request for order <strong dir=\"ltr\">{{ name }}</strong>. Our team will review it and get back to you shortly, usually within 1-2 business days.",
                  "شكراً، استلمنا طلب الاسترجاع الخاص بالطلب رقم <strong dir=\"ltr\">{{ name }}</strong>. سيراجعه فريقنا ويتواصل معك قريباً، عادةً خلال يوم إلى يومين عمل."))
            + p(t("Please keep the items unused, with tags and original packaging.", "يُرجى الاحتفاظ بالمنتجات دون استخدام وبالبطاقات والتغليف الأصلي."), muted=True)
            + status_button())


def return_request_approved():
    return (t("Your return for order {{ name }} is approved", "تمت الموافقة على استرجاع الطلب {{ name }}"),
            t("Your return is approved. Here's what happens next.", "تمت الموافقة على الاسترجاع. إليك الخطوات التالية."),
            h1(t("Your return is approved", "تمت الموافقة على طلب الاسترجاع")) + greeting()
            + p(t("Good news: your return request for order <strong dir=\"ltr\">{{ name }}</strong> has been approved.",
                  "خبر سعيد: تمت الموافقة على طلب الاسترجاع الخاص بالطلب رقم <strong dir=\"ltr\">{{ name }}</strong>."))
            + box(t("<strong>Next steps</strong><br>1. Pack the items unused, with tags and original packaging.<br>"
                    "2. Our courier will contact you to collect them, or follow any return instructions included in this email.<br>"
                    "3. Once we receive and check the items, we'll issue your refund or exchange.",
                    "<strong>الخطوات التالية</strong><br>1. غلّف المنتجات دون استخدام وبالبطاقات والتغليف الأصلي.<br>"
                    "2. سيتواصل معك مندوبنا لاستلامها، أو اتبع تعليمات الاسترجاع المرفقة بهذه الرسالة.<br>"
                    "3. بعد استلام المنتجات وفحصها سنقوم برد المبلغ أو الاستبدال."), border=BLUE)
            + status_button())


def return_request_declined():
    return (t("Update on your return request for order {{ name }}", "تحديث بخصوص طلب استرجاع الطلب {{ name }}"),
            t("We couldn't approve your return request.", "لم نتمكن من الموافقة على طلب الاسترجاع."),
            h1(t("We couldn't approve your return", "لم نتمكن من قبول طلب الاسترجاع")) + greeting()
            + p(t("We've reviewed your return request for order <strong dir=\"ltr\">{{ name }}</strong> and unfortunately can't accept it. "
                  "This usually happens when the 7-day window has passed or items were used.",
                  "راجعنا طلب الاسترجاع الخاص بالطلب رقم <strong dir=\"ltr\">{{ name }}</strong> وللأسف لا يمكننا قبوله. "
                  "يحدث ذلك عادةً عند تجاوز مدة الـ7 أيام أو إذا كانت المنتجات مستخدمة."))
            + p(t("If you think this is a mistake, message us on WhatsApp and we'll take another look.",
                  "إذا كنت ترى أن هناك خطأ، راسلنا على واتساب وسنراجع الطلب مرة أخرى."))
            + button(WA_LINK, t("Message us on WhatsApp", "راسلنا على واتساب")))


def abandoned_checkout():
    promo = ("{% comment %} Optional discount: put a real discount code between the quotes, e.g. 'COMEBACK10'. Leave empty to hide. {% endcomment %}\n"
             "{% assign bs_promo_code = '' %}\n"
             "{% if bs_promo_code != blank %}"
             + box(t("<strong>A little extra:</strong> use code <strong dir=\"ltr\" style=\"letter-spacing:1px;\">{{ bs_promo_code }}</strong> at checkout for a discount on your order.",
                     "<strong>هدية صغيرة:</strong> استخدم الكود <strong dir=\"ltr\" style=\"letter-spacing:1px;\">{{ bs_promo_code }}</strong> عند إتمام الطلب للحصول على خصم."),
                   bg="#FFF6DD", border=YELLOW)
             + "{% endif %}\n")
    return (t("You left something in your cart", "نسيت شيئاً في سلتك"),
            t("Your cart is saved. Complete your order with cash on delivery.", "سلتك محفوظة. أكمل طلبك والدفع عند الاستلام."),
            h1(t("Your gear is waiting for you", "معداتك في انتظارك")) + greeting("billing_address.first_name")
            + p(t("You left some items in your cart. We've saved them for you; finish your order in a minute and pay cash on delivery.",
                  "تركت بعض المنتجات في سلتك وقد حفظناها لك. أكمل طلبك في دقيقة وادفع عند الاستلام."))
            + promo + button("{{ url }}", t("Complete your order", "أكمل طلبك"))
            + p(t("Stock is limited and items aren't reserved until you order.", "الكميات محدودة ولا يتم حجز المنتجات إلا بعد إتمام الطلب."), muted=True, size=13)
            + h2(t("Your cart", "سلتك")) + line_items("line_items", "checkout")
            + kv_rows([(t("Subtotal", "المجموع الفرعي"), money("subtotal_price"), None)])
            + button("{{ url }}", t("Return to checkout", "العودة لإتمام الطلب"), bg=YELLOW, fg=INK))


def customer_account_invite():
    return (t("Activate your Baba Saleh account", "فعّل حسابك في بابا صالح"),
            t("Create your password to start tracking orders.", "أنشئ كلمة المرور لتبدأ متابعة طلباتك."),
            h1(t("You're invited to create an account", "أنت مدعو لإنشاء حساب")) + greeting()
            + "{% if custom_message != blank %}" + box('<div dir="auto">{{ custom_message }}</div>') + "{% endif %}"
            + p(t("Activate your account to track orders, save addresses and check out faster.",
                  "فعّل حسابك لتتابع طلباتك وتحفظ عناوينك وتُكمل طلباتك بشكل أسرع."))
            + button("{{ customer.account_activation_url }}", t("Activate account", "تفعيل الحساب"))
            + p(t("If you didn't expect this invitation, you can ignore this email.", "إذا لم تكن تنتظر هذه الدعوة يمكنك تجاهل الرسالة."), muted=True, size=13))


def customer_account_welcome():
    return (t("Welcome to Baba Saleh", "أهلاً بك في بابا صالح"),
            t("Your account is active. Gear up!", "حسابك مُفعّل. جهّز نفسك!"),
            h1(t("Welcome to Baba Saleh!", "أهلاً بك في بابا صالح!")) + greeting()
            + p(t("Your account is now active. Next time you shop, log in to check out faster and follow your orders.",
                  "تم تفعيل حسابك. في المرة القادمة سجّل الدخول لتُكمل طلبك أسرع وتتابع طلباتك."))
            + box(t("Cash on delivery &nbsp;·&nbsp; Shipping to all governorates &nbsp;·&nbsp; 7-day returns",
                    "الدفع عند الاستلام &nbsp;·&nbsp; شحن لجميع المحافظات &nbsp;·&nbsp; استرجاع خلال 7 أيام"), border=YELLOW)
            + button(SITE, t("Start shopping", "ابدأ التسوق")))


def customer_password_reset():
    return (t("Reset your Baba Saleh password", "إعادة تعيين كلمة المرور في بابا صالح"),
            t("Use the link inside to choose a new password.", "استخدم الرابط بالداخل لاختيار كلمة مرور جديدة."),
            h1(t("Reset your password", "إعادة تعيين كلمة المرور")) + greeting()
            + p(t("We received a request to reset your password. Click the button below to choose a new one.",
                  "تلقّينا طلباً لإعادة تعيين كلمة المرور. اضغط على الزر بالأسفل لاختيار كلمة مرور جديدة."))
            + button("{{ customer.reset_password_url }}", t("Reset password", "إعادة تعيين كلمة المرور"))
            + p(t("If you didn't ask for this, you can safely ignore this email; your password won't change.",
                  "إذا لم تطلب ذلك يمكنك تجاهل هذه الرسالة بأمان، ولن تتغير كلمة المرور."), muted=True, size=13))


def customer_marketing_confirmation():
    return (t("Confirm your subscription to Baba Saleh", "أكّد اشتراكك في بابا صالح"),
            t("One click to get new arrivals and offers first.", "ضغطة واحدة لتصلك المنتجات الجديدة والعروض أولاً."),
            h1(t("Confirm your subscription", "أكّد اشتراكك")) + greeting()
            + p(t("Thanks for signing up! Confirm your email to get new arrivals, flash sales and exclusive offers first.",
                  "شكراً لاشتراكك! أكّد بريدك الإلكتروني لتصلك المنتجات الجديدة وعروض الفلاش والعروض الحصرية أولاً."))
            + button("{{ confirmation_url }}", t("Confirm subscription", "تأكيد الاشتراك"))
            + p(t("If you didn't sign up, ignore this email and you won't be subscribed.", "إذا لم تشترك، تجاهل هذه الرسالة ولن يتم اشتراكك."), muted=True, size=13))


def contact_customer():
    return (t("A message from Baba Saleh", "رسالة من بابا صالح"),
            t("A message from the Baba Saleh team.", "رسالة من فريق بابا صالح."),
            "{% if customer.first_name != blank %}" + greeting() + "{% endif %}"
            + p('<span dir="auto">{{ email_body | newline_to_br }}</span>')
            + p(t("The Baba Saleh team", "فريق بابا صالح"), muted=True))


def gift_card_created():
    return (t("Your Baba Saleh gift card", "بطاقة الهدايا من بابا صالح"),
            t("Here's your gift card. Use it at checkout.", "إليك بطاقة الهدايا، استخدمها عند إتمام الطلب."),
            h1(t("Here's your gift card!", "إليك بطاقة الهدايا!")) + greeting()
            + "{% if gift_card.message != blank %}" + box('<div dir="auto">{{ gift_card.message }}</div>', border=YELLOW) + "{% endif %}"
            + f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0;">
<tr><td bgcolor="{INK}" align="center" style="background:{INK};border-radius:14px;padding:26px 18px;font-family:{ff()};">
  <div style="font-size:13px;color:{YELLOW};font-weight:700;letter-spacing:1px;text-transform:uppercase;">{t("Gift card", "بطاقة هدايا")}</div>
  <div style="font-size:32px;font-weight:700;color:#FFFFFF;margin:6px 0;">{money("gift_card.initial_value")}</div>
  <div dir="ltr" style="font-family:'Courier New',monospace;font-size:20px;letter-spacing:2px;color:#FFFFFF;background:#27272A;border-radius:8px;padding:10px 14px;display:inline-block;">{{{{ gift_card.code }}}}</div>
</td></tr></table>
"""
            + p(t("Enter this code at checkout. Your balance carries over if you don't use it all at once.",
                  "أدخل هذا الكود عند إتمام الطلب، ويُحفظ الرصيد المتبقي إذا لم تستخدمه بالكامل."))
            + "{% if gift_card.expires_on %}" + p(t("Expires on ", "تنتهي صلاحيتها في ") + '<span dir="ltr">{{ gift_card.expires_on | date: "%d/%m/%Y" }}</span>.', muted=True, size=13) + "{% endif %}"
            + "{% if gift_card.url != blank %}" + button("{{ gift_card.url }}", t("View gift card", "عرض بطاقة الهدايا")) + "{% endif %}"
            + button(SITE, t("Start shopping", "ابدأ التسوق"), bg=YELLOW, fg=INK))


# ---- Staff ----
def new_order():
    return (t("[Baba Saleh] New order {{ name }}", "[بابا صالح] طلب جديد {{ name }}"),
            t("New order {{ name }} for {{ total_price | money }}", "طلب جديد {{ name }} بقيمة {{ total_price | money }}"),
            h1(t("New order {{ name }}", "طلب جديد {{ name }}"))
            + p(t("<strong>{{ customer.name | default: billing_address.name }}</strong> placed an order for <strong>" + money("total_price") + "</strong>.",
                  "قام <strong>{{ customer.name | default: billing_address.name }}</strong> بطلب بقيمة <strong>" + money("total_price") + "</strong>."))
            + button(ADMIN + "/orders/{{ id }}", t("Open in Shopify admin", "فتح الطلب في لوحة Shopify"))
            + order_meta()
            + kv_rows([(t("Customer email", "بريد العميل"), '<span dir="ltr">{{ email }}</span>', "email != blank"),
                       (t("Phone", "الهاتف"), '<span dir="ltr">{{ shipping_address.phone | default: phone }}</span>', "shipping_address.phone != blank or phone != blank"),
                       (t("Customer note", "ملاحظة العميل"), "{{ note }}", "note != blank")])
            + h2(t("Items", "المنتجات")) + line_items() + totals() + shipping_block(), True)


def return_request():
    return (t("[Baba Saleh] Return requested for order {{ name }}", "[بابا صالح] طلب استرجاع للطلب {{ name }}"),
            t("A customer requested a return.", "عميل طلب استرجاع."),
            h1(t("New return request", "طلب استرجاع جديد"))
            + p(t("A return was requested for order <strong dir=\"ltr\">{{ name }}</strong>"
                  "{% if customer.name != blank %} by <strong>{{ customer.name }}</strong>{% endif %}. Review it and approve or decline in Shopify admin.",
                  "تم طلب استرجاع للطلب رقم <strong dir=\"ltr\">{{ name }}</strong>"
                  "{% if customer.name != blank %} من <strong>{{ customer.name }}</strong>{% endif %}. راجعه ووافق عليه أو ارفضه من لوحة Shopify."))
            + button(ADMIN + "/orders?query={{ name | url_encode }}", t("Open in Shopify admin", "فتح في لوحة Shopify")), True)


# --------------------------------------------------------------------------
# Registry: file, admin section, admin name, builder
# --------------------------------------------------------------------------
CUSTOMER, STAFF = "Customer notifications", "Staff notifications"
NOTIFICATIONS = [
    ("order_confirmation", CUSTOMER, "Order processing > Order confirmation", order_confirmation),
    ("draft_order_invoice", CUSTOMER, "Order processing > Draft order invoice", draft_order_invoice),
    ("shipping_confirmation", CUSTOMER, "Order processing > Shipping confirmation", shipping_confirmation),
    ("ready_for_local_pickup", CUSTOMER, "Local pickup > Ready for local pickup", ready_for_local_pickup),
    ("picked_up_by_customer", CUSTOMER, "Local pickup > Picked up by customer", picked_up_by_customer),
    ("order_edited", CUSTOMER, "Order exceptions > Order edited", order_edited),
    ("order_invoice", CUSTOMER, "Order exceptions > Order invoice", order_invoice),
    ("order_canceled", CUSTOMER, "Order exceptions > Order canceled", order_canceled),
    ("order_refund", CUSTOMER, "Order exceptions > Order refund", order_refund),
    ("order_payment_receipt", CUSTOMER, "Order exceptions > Order payment receipt", order_payment_receipt),
    ("shipping_update", CUSTOMER, "Shipping updates > Shipping update", shipping_update),
    ("out_for_delivery", CUSTOMER, "Shipping updates > Out for delivery", out_for_delivery),
    ("delivered", CUSTOMER, "Shipping updates > Delivered", delivered),
    ("return_request_confirmation", CUSTOMER, "Returns > Return request confirmation (if listed)", return_request_confirmation),
    ("return_request_approved", CUSTOMER, "Returns > Return request approved", return_request_approved),
    ("return_request_declined", CUSTOMER, "Returns > Return request declined", return_request_declined),
    ("abandoned_checkout", CUSTOMER, "Marketing > Abandoned checkout", abandoned_checkout),
    ("customer_marketing_confirmation", CUSTOMER, "Marketing > Customer marketing confirmation", customer_marketing_confirmation),
    ("customer_account_invite", CUSTOMER, "Customer accounts > Customer account invite", customer_account_invite),
    ("customer_account_welcome", CUSTOMER, "Customer accounts > Customer account welcome", customer_account_welcome),
    ("customer_password_reset", CUSTOMER, "Customer accounts > Customer account password reset", customer_password_reset),
    ("contact_customer", CUSTOMER, "Customer accounts > Contact customer", contact_customer),
    ("gift_card_created", CUSTOMER, "Gift cards > Gift card created", gift_card_created),
    ("new_order", STAFF, "New order", new_order),
    ("return_request", STAFF, "Return request", return_request),
]


BLOCKS = {"if": "endif", "unless": "endunless", "for": "endfor", "case": "endcase",
          "capture": "endcapture", "comment": "endcomment"}
BANNED = ("render", "include", "section", "schema", "javascript")


def check(name, html):
    """Fail the build on unbalanced Liquid blocks, unclosed tags, snippets or HTML table mismatches."""
    import re
    errors, stack = [], []
    if re.search(r"\{\{(?![^{}]*\}\})|\{%(?![^{}]*%\})", html):
        errors.append("unclosed {{ or {%")
    if "{{{" in html or "}}}" in html:
        errors.append("stray triple brace")
    for m in re.finditer(r"\{%-?\s*(\w+)", html):
        tag = m.group(1)
        if stack and stack[-1] == "comment" and tag != "endcomment":
            continue
        if tag in BANNED:
            errors.append(f"unsupported tag {tag}")
        elif tag in BLOCKS:
            stack.append(tag)
        elif tag.startswith("end"):
            if not stack or BLOCKS[stack[-1]] != tag:
                errors.append(f"unexpected {tag} (open: {stack})")
            else:
                stack.pop()
        elif tag in ("else", "elsif", "when") and not stack:
            errors.append(f"{tag} outside block")
    if stack:
        errors.append(f"unclosed blocks {stack}")
    for el in ("table", "tr", "td", "a", "div", "p", "h1", "h2", "span", "strong", "s"):
        opened = len(re.findall(rf"<{el}[\s>]", html))
        closed = html.count(f"</{el}>")
        if opened != closed:
            errors.append(f"<{el}> {opened} open vs {closed} closed")
    if errors:
        raise SystemExit(f"{name}: " + "; ".join(errors))


def build():
    global LANG
    rows = []
    for lang in ("en", "ar"):
        LANG = lang
        (OUT / lang).mkdir(exist_ok=True)
        for fname, section, admin_name, fn in NOTIFICATIONS:
            res = fn()
            title, pre, body = res[:3]
            staff = len(res) > 3 and res[3]
            html = page(title, pre, body, staff)
            check(f"{lang}/{fname}", html)
            (OUT / lang / f"{fname}.liquid").write_text(html, encoding="utf-8")
            if lang == "en":
                rows.append([fname, section, admin_name, title])
            else:
                rows[[r[0] for r in rows].index(fname)].append(title)
    # Bilingual: one email with the English block, then the Arabic block (RTL).
    (OUT / "bilingual").mkdir(exist_ok=True)
    for row, (fname, section_name, admin_name, fn) in zip(rows, NOTIFICATIONS):
        parts, pres = [], []
        for lang in ("en", "ar"):
            LANG = lang
            res = fn()
            parts.append((lang, res[2]))
            pres.append(res[1])
            staff = len(res) > 3 and res[3]
        LANG = "en"
        subject = f"{row[3]} | {row[4]}"
        html = page(subject, " | ".join(pres), parts, staff)
        check(f"bilingual/{fname}", html)
        (OUT / "bilingual" / f"{fname}.liquid").write_text(html, encoding="utf-8")
        row.append(subject)
    (OUT / "README.md").write_text(readme(rows), encoding="utf-8")
    print(f"Wrote {len(rows) * 3} templates + README.md")


def readme(rows):
    esc = lambda x: x.replace("|", "\\|")
    table = "\n".join(f"| `{f}.liquid` | {s.split()[0]} | {n} | `{esc(bi)}` |" for f, s, n, en, ar, bi in rows)
    return f"""# Baba Saleh - Shopify notification emails

Branded HTML email templates (English + Arabic RTL) for Shopify **Settings > Notifications**.
Generated by `build.py` - **edit `build.py`, then run `python3 notifications/build.py`**; never hand-edit the `.liquid` files.

- **`bilingual/` (recommended): one email with English and Arabic together** - paste these and you are done.
- `en/` English only, `ar/` Arabic only (same file names, same design) - only if you prefer per-language emails.
- Each file is a full, self-contained template (no snippets) - paste the whole file.

## Files

| File | Type | Shopify admin notification | Subject (bilingual) |
|---|---|---|---|
{table}

## Paste a template

1. Shopify admin > **Settings > Notifications > Customer notifications** (or **Staff notifications** for `new_order` / `return_request`).
2. Open the notification named in the table, click **Edit code**.
3. Replace the **Subject** with the subject from the table, and replace the whole **Email body (HTML)** with the file contents.
4. Click **Preview** (check desktop and mobile), then **Save**.
5. Send yourself a test: back on the notification page use **Send test email** (staff notifications: **Send test notification** next to the recipient).

## Separate Arabic version (only if not using bilingual/)

Customers get the notification in the language they shopped in, once Arabic is a published store language.

- **Settings > Notifications > Customer notifications**, open a notification, use the **language selector** (top of the editor) to switch to *Arabic*, **Edit code**, paste the file from `ar/` and the Arabic subject, **Save**.
- If your admin has no selector there: open the **Translate & Adapt** app > **Notifications**, choose Arabic, and paste the `ar/` subject and body for each notification.
- Staff notifications use the staff member's admin language; use `en/` unless your staff use Arabic admin.

## Checks before going live

- **Abandoned checkout discount (optional):** in `abandoned_checkout.liquid` set `{{% assign bs_promo_code = '' %}}` to a real, active discount code (e.g. `'COMEBACK10'`) - or change it in `build.py` and rebuild.
- **Variables:** templates follow Shopify's default notification variables (guarded with `if`/`default` so a missing value hides cleanly). After pasting, preview each one. For *Customer marketing confirmation* (`confirmation_url`), *Contact customer* (`email_body`) and the *Returns* emails, compare with the variable list in Shopify's code editor and the default template (Revert to default shows it) if the preview looks empty.
- **Returns:** names of return notifications vary by admin version; skip any file whose notification isn't listed (e.g. *Return request confirmation*).
- **Logo:** the logo sits on a white chip, so it works in light and dark mode. If the logo file URL changes, update `LOGO` in `build.py`.
"""


if __name__ == "__main__":
    build()

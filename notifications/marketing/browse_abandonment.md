# "See something you liked?" email (browse abandonment)

Shopify sends this from **Marketing > Automations > Recover abandoned browse** (built in Shopify's email editor, so it can't be pasted as code). Open the automation, click the email, and replace the texts below. More text and fewer images = less spam.

**Subject:** `Still thinking about it? | لسه بتفكر فيه؟`
**Preview text:** `The item you viewed is still available, with cash on delivery. | المنتج اللي شفته لسه متاح، والدفع عند الاستلام.`

**Heading:** `Still thinking about it? | لسه بتفكر فيه؟`

**Text block (under the heading):**

Hi {{ customer.first_name | default: "there" }},

You were looking at this at Baba Saleh Sports. It's still available, but stock is limited.
Order online and pay cash on delivery, with delivery to all governorates and 7-day returns.

أهلاً {{ customer.first_name }}،

كنت بتتفرج على المنتج ده في بابا صالح للرياضة، ولسه متاح بس الكمية محدودة.
اطلب أونلاين وادفع عند الاستلام، مع توصيل لكل المحافظات واسترجاع خلال 7 أيام.

**Product block:** keep the one product block (1 image). Delete any extra image or banner blocks.

**Button:** `View product | شوف المنتج`

**Text block (bottom):**

Questions? WhatsApp us on +20 102 830 5495 or visit one of our 5 branches.
عندك سؤال؟ كلمنا واتساب على 01028305495 أو زور أي فرع من فروعنا الخمسة.

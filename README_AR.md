# برق نيوز v14.5

## إدارة المفاتيح

هذه النسخة لا تحتوي أي مفتاح أو رمز دخول داخل الكود أو الملفات.

يقرأ التطبيق القيم التالية من Streamlit Secrets فقط:

- MASSIVE_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- OPENAI_API_KEY

أضف القيم من:
Manage app → Settings → Secrets

لا تنشئ ملف secrets.toml داخل المستودع، ولا ترفع ملفات البيئة أو مفاتيح API إلى GitHub.

## الحماية

يتضمن المشروع `.gitignore` لمنع رفع:

- `.streamlit/secrets.toml`
- `.env`
- `secrets.toml`
- ملفات Python المؤقتة

## ملاحظة مهمة

تنظيف الملفات الحالية لا يحذف أسرارًا ظهرت في سجل Git السابق. أي مفتاح ظهر في تنبيه GitHub يجب إلغاؤه وإنشاء مفتاح جديد.

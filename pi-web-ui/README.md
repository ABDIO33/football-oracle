# 🎯 Pi Web UI — واجهة رسومية لـ Pi Coding Agent

**وداعاً للتيرمينال!** واجهة ويب جميلة لكل مزايا pi بدون أي خسائر.

## ✨ المميزات

- ✅ **جميع مزايا pi** — Tools, Skills, Extensions — بدون فقدان
- ✅ **واجهة نيون سايبربانك** مع دعم كامل للعربية (RTL)
- ✅ **WebSocket مباشر** — استجابة فورية بدون تأخير
- ✅ **Markdown + Code Highlighting** — عرض جميل للكود
- ✅ **Tool Calls مرئية** — شوف ماذا يفعل AI خطوة بخطوة
- ✅ **Thinking Blocks** — شوف تفكير الـ AI
- ✅ **أوامر pi كاملة** — /model, /settings, /compact, /session ...
- ✅ **Bash مباشر** — !command
- ✅ **جلسات متعددة** — new session, abort, follow-up

## 🚀 التشغيل

### سريع:
```
C:\Users\zake.exe\Desktop\Score Exact 100\pi-web-ui\start.bat
```

### أو يدوياً:
```bash
cd "C:\Users\zake.exe\Desktop\Score Exact 100\pi-web-ui"
npm start
```

ثم افتح المتصفح على:
```
http://localhost:3456
```

## 🎮 كيفية الاستخدام

| الميزة | الطريقة |
|--------|---------|
| **إرسال رسالة** | اكتب و Enter أو اضغط زر الإرسال |
| **سطر جديد** | Shift + Enter |
| **أمر Bash** | `!ls -la` |
| **أمر Pi** | `/model` , `/settings` , `/compact` |
| **إرفاق ملف** | زر 📎 |
| **إيقاف** | زر ■ إيقاف أو Escape |
| **جلسة جديدة** | زر 📄 |
| **إشارة لملف** | اكتب `@` |
| **تغيير النموذج** | `/model` |
| **الإعدادات** | `/settings` |

## 🔗 مع football predictor

ممكن تفتحه جنباً إلى جنب مع مشروع التوقعات:
- http://localhost:5000 — Football Predictor
- http://localhost:3456 — Pi Web UI Chat

## ⚙️ ملاحظات

- يستخدم نفس إعدادات pi الموجودة (`~/.pi/agent/`)
- جميع المفاتيح والمصادقة محفوظة
- 153+ نموذج متاح (DeepSeek, Anthropic, OpenAI, Google...)

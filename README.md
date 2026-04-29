# Test Bot - Fly.io deploy

## Muammo nima edi?
1. `requirements.txt` yo'q edi → `ModuleNotFoundError: No module named 'aiogram'`
2. `fly.toml` da `[http_service]` bo'lgan, lekin bot HTTP server emas → "instance refused connection on 8080"

## Tuzatildi
- `requirements.txt` qo'shildi (aiogram, pytz, Pillow)
- `Dockerfile` to'g'ri sozlandi
- `fly.toml` dan HTTP service olib tashlandi (bot polling ishlatadi)

## Deploy qilish
```bash
fly deploy
```

## Eslatma
SQLite bazasi (`bot_data.db`) machine restart bo'lganda yo'qolmasligi uchun volume ulang:
```bash
fly volumes create bot_data --region ams --size 1
```
Va `bot.py` dagi `DB_NAME = "bot_data.db"` ni `DB_NAME = "/app/data/bot_data.db"` ga o'zgartiring.

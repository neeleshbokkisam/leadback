# leadback

discord feedback bot. categorizes messages with spacy, stores in redis, serves a small flask dashboard.

## setup

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
docker compose up -d
cp .env.example .env
```

fill in `DISCORD_TOKEN` and `FEEDBACK_CHANNEL_ID` in `.env`.

## run

```bash
python bot/main.py
python api/app.py
```

dashboard at http://localhost:5000

notion and slack forwarding work if you add those env vars. otherwise skipped.

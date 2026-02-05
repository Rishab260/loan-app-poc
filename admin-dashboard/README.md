# admin-dashboard

Purpose: simple UI to view loan decisions (reads from templates or subscribes to Redis for live updates).

Run locally:

```bash
cd admin-dashboard
AWS_REGION=us-east-1 AWS_PROFILE=rishab python main.py
# then open the app in your browser at the configured port
```

Templates are under `templates/` (admin.html). The Dockerfile builds an image used by docker-compose.

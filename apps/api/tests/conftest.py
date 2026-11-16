import os

# Settings are read at import time, so set safe test values before the app is imported.
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
# A fixed, test-only Fernet key.
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "dGVzdC1vbmx5LWtleS1kby1ub3QtdXNlLTMyYnl0ZXM=")

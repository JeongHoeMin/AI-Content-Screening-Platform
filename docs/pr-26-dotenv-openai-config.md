# PR-26 dotenv OpenAI Configuration

## Summary

OpenAI mode optionally reads the repository-root `.env` before validating the
existing OpenAI configuration. Mock mode never loads dotenv or OpenAI config.

## Configuration

The loader uses the path derived from `app/config/openai.py`, so it does not
depend on the terminal's current directory. It loads the optional file with
`override=False`; exported shell variables therefore take precedence.

```dotenv
OPENAI_API_KEY="..."
OPENAI_MODEL="gpt-4o-mini"
OPENAI_TIMEOUT_SECONDS="60"
OPENAI_MAX_RETRIES="2"
```

`.env` is ignored by Git and must not be committed. A missing `.env` is normal;
configuration fails only when the final merged environment has no API key or
contains invalid OpenAI configuration values.

## Failure policy

If an existing dotenv file cannot be read and dotenv raises `OSError`, config
loading raises a safe `ConfigurationError` without exposing the file contents,
path details, or API key. Dotenv loading occurs only while the OpenAI workflow
is assembled, never at import time.

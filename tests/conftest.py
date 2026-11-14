import os
import tempfile

# Must run before anything imports utils.config, so tests never touch real data or real keys.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="repomind-test-")
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["APP_ENV"] = "test"
os.environ["ACCESS_KEY"] = ""
os.environ["RATE_LIMIT_INDEX_PER_HOUR"] = "0"
os.environ["RATE_LIMIT_QUERY_PER_MINUTE"] = "0"

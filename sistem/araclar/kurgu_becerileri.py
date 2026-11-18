"""List the available skill IDs and reference paths for specialist tasks."""
import json
from kurgu_plan import beceriler

if __name__ == "__main__":
    print(json.dumps(beceriler(), ensure_ascii=False, indent=2))

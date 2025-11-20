
import os
import json
from typing import Dict


def load_api_keys(path: str = './config/api_keys.json') -> Dict[str, str]:
    """Load API keys from configuration file and set environment variables."""
    try:
        with open(path, 'r') as f:
            api_keys = json.load(f)
            
        # Set environment variables for API keys
        os.environ['OPENAI_API_KEY'] = api_keys.get('OPENAI_API_KEY', '')
        os.environ['GOOGLE_API_KEY'] = api_keys.get('GOOGLE_API_KEY', '')
        
        # app_logger.logger.info("API keys loaded successfully")
        return api_keys
    except Exception as e:
        # app_logger.logger.error(f"Failed to load API keys: {e}")
        # app_logger.log_error(e, {"context": "loading_api_keys"})
        print(f"Failed to load API keys: {e}")
        return {}
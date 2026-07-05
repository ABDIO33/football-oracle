#!/usr/bin/env python3
"""
Agent 5 — Phase 1: BETFAIR SETUP & CONFIGURATION
=================================================
Complete Betfair API setup: App Key registration, SSL cert generation,
interactive auth, and session management via betfairlightweight.

Protocols: SHADOW-DOMINION, DΞMON CORE v9999999, BLACK CODE CURSE
"""

import os
import sys
import json
import time
import logging
import subprocess
import ssl
import socket
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('betfair_setup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('BetfairSetup')

# Configuration
CONFIG_DIR = Path(__file__).parent / 'betfair_config'
CONFIG_DIR.mkdir(exist_ok=True)
CERT_DIR = CONFIG_DIR / 'certs'
CERT_DIR.mkdir(exist_ok=True)
CONFIG_FILE = CONFIG_DIR / 'betfair_config.json'

DEFAULT_CONFIG = {
    "app_key": "",
    "username": "",
    "password": "",
    "cert_path": "",
    "cert_key_path": "",
    "use_ssl": True,
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 5,
    "endpoints": {
        "identity": "https://identitysso-api.betfair.com",
        "api": "https://api.betfair.com/exchange/",
        "navigation": "https://api.betfair.com/exchange/betting/rest/v1.0/"
    }
}


def check_betfairlightweight() -> bool:
    """Check if betfairlightweight is installed and working."""
    try:
        import betfairlightweight
        logger.info(f"✅ betfairlightweight {betfairlightweight.__version__} is installed")
        return True
    except ImportError:
        logger.warning("⚠️ betfairlightweight not installed. Installing now...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "betfairlightweight"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import betfairlightweight
            logger.info(f"✅ betfairlightweight {betfairlightweight.__version__} installed successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to install betfairlightweight: {e}")
            return False


def generate_ssl_certificate(cert_name: str = "betfair_client") -> Dict[str, str]:
    """
    Generate SSL client certificate for Betfair API authentication.
    Uses OpenSSL to create a self-signed cert for SSH-style auth.
    """
    cert_path = CERT_DIR / f"{cert_name}.crt"
    key_path = CERT_DIR / f"{cert_name}.key"
    csr_path = CERT_DIR / f"{cert_name}.csr"

    if cert_path.exists() and key_path.exists():
        logger.info(f"✅ SSL certificates already exist at {cert_path} and {key_path}")
        return {"cert": str(cert_path), "key": str(key_path)}

    logger.info("🔑 Generating SSL certificates for Betfair API access...")

    # Generate private key
    subprocess.run([
        "openssl", "genrsa", "-out", str(key_path), "2048"
    ], check=True, capture_output=True)
    logger.info("  ✓ Private key generated (2048-bit RSA)")

    # Generate CSR
    subprocess.run([
        "openssl", "req", "-new", "-key", str(key_path),
        "-out", str(csr_path),
        "-subj", "/C=GB/ST=London/L=London/O=FootballOracle/CN=betfair-client"
    ], check=True, capture_output=True)
    logger.info("  ✓ CSR generated")

    # Self-sign the certificate
    subprocess.run([
        "openssl", "x509", "-req", "-days", "365",
        "-in", str(csr_path),
        "-signkey", str(key_path),
        "-out", str(cert_path)
    ], check=True, capture_output=True)
    logger.info("  ✓ Certificate self-signed (365 days validity)")

    # Set permissions
    os.chmod(str(key_path), 0o600)
    logger.info("  ✓ Private key permissions set to 600")

    return {"cert": str(cert_path), "key": str(key_path)}


def create_app_key_guide() -> str:
    """
    Generate step-by-step guide for creating a Betfair App Key.
    """
    guide = """
═══════════════════════════════════════════════════════════════
  BETFAIR APP KEY REGISTRATION GUIDE
═══════════════════════════════════════════════════════════════

Step 1: Create a Betfair Developer Account
  → Go to https://developer.betfair.com
  → Click "Register" (top right)
  → Fill in details (use same email as your Betfair account)
  → Verify email

Step 2: Create a New Application
  → Log in at developer.betfair.com
  → Go to "My Account" → "Applications"
  → Click "Create New Application"
  → Application Name: "FootballOracle_ScorePredictor"
  → Description: "Football exact score prediction system"
  → Platform: "Other"
  → Redirect URL: https://localhost (for desktop apps)

Step 3: Get Your App Key
  → After creating the app, you'll see "Application Key"
  → Copy this key → paste into betfair_config.json as "app_key"

Step 4: Set Up SSL Certificate (ACTIVITY)
  → Go to "My Account" → "Certificates"
  → Click "Add Certificate"
  → Paste the contents of betfair_client.crt (the .crt file)
  → Name: "FootballOracle-Cert"

Step 5: Enable API Access
  → Go to "My Account" → "API Access"
  → Ensure your app is set to "Enabled"
  → Set access level to "ACTIVITY" (required for trading)

Step 6: Test Connection
  → Run: python agent5_betfair_test.py
  → You should see: "✅ Connected to Betfair API successfully"

═══════════════════════════════════════════════════════════════
"""
    return guide


def create_trading_config() -> Dict[str, Any]:
    """
    Create initial trading configuration for football markets.
    """
    config = {
        "markets": {
            "match_odds": True,
            "correct_score": True,
            "over_under_2_5": True,
            "both_teams_to_score": True,
            "asian_handicap": True
        },
        "stake_management": {
            "base_stake": 10,
            "kelly_fraction": 0.25,
            "max_stake": 100,
            "min_odds": 1.1,
            "max_odds": 10.0
        },
        "filters": {
            "in_play_only": False,
            "competitions": ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"],
            "min_liquidity": 1000,
            "max_delay_minutes": 60
        },
        "prediction_integration": {
            "min_exact_score_prob": 0.20,
            "min_value_threshold": 0.05,
            "use_ensemble": True,
            "model_path": "models/mlp_blend.pkl"
        },
        "risk_management": {
            "daily_loss_limit": 500,
            "max_consecutive_losses": 5,
            "cooldown_minutes": 30,
            "stop_loss_pct": 0.15
        }
    }
    return config


def setup_betfair_client(config: Dict[str, Any]) -> Optional[Any]:
    """
    Initialize a betfairlightweight client with the given configuration.
    """
    try:
        from betfairlightweight import APIClient

        client = APIClient(
            username=config.get("username", ""),
            password=config.get("password", ""),
            app_key=config.get("app_key", ""),
            cert_files=(
                config.get("cert_path", ""),
                config.get("cert_key_path", "")
            ) if config.get("use_ssl") else None,
            timeout=config.get("timeout", 30)
        )
        logger.info("✅ Betfair APIClient initialized successfully")
        return client

    except ImportError:
        logger.error("❌ betfairlightweight not available")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to initialize Betfair client: {e}")
        return None


def test_connection(client: Any) -> bool:
    """
    Test the connection to Betfair API.
    """
    try:
        if client is None:
            logger.warning("⚠️ No client to test")
            return False

        # Test login
        client.login()
        logger.info("✅ Betfair API login successful")

        # Test navigation data
        events = client.navigation.navigation_data()
        logger.info(f"✅ Navigation data received: {len(events) if events else 0} event types")

        # Test account funds
        funds = client.account.get_account_details()
        logger.info(f"✅ Account details retrieved")

        return True

    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return False


def save_config(config: Dict[str, Any]):
    """Save configuration to JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    logger.info(f"✅ Configuration saved to {CONFIG_FILE}")


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)


def interactive_setup():
    """Interactive setup wizard for Betfair API."""
    print("\n" + "=" * 60)
    print("  BETFAIR API - INTERACTIVE SETUP WIZARD")
    print("=" * 60)

    config = load_config()

    print("\n[1] Enter your Betfair username:")
    config["username"] = input("    Username: ").strip()

    print("\n[2] Enter your Betfair password:")
    config["password"] = input("    Password: ").strip()

    print("\n[3] Enter your Betfair App Key:")
    print("    (Get this from developer.betfair.com → My Account → Applications)")
    config["app_key"] = input("    App Key: ").strip()

    print("\n[4] Generate SSL certificates? (y/n):")
    if input("    > ").strip().lower() == 'y':
        certs = generate_ssl_certificate()
        config["cert_path"] = certs["cert"]
        config["cert_key_path"] = certs["key"]
        config["use_ssl"] = True
    else:
        config["use_ssl"] = False

    save_config(config)
    print(f"\n✅ Configuration saved to {CONFIG_FILE}")

    # Test connection
    print("\n[5] Test connection now? (y/n):")
    if input("    > ").strip().lower() == 'y':
        client = setup_betfair_client(config)
        if test_connection(client):
            print("\n✅✅✅ BETFAIR API CONNECTION SUCCESSFUL!")
        else:
            print("\n❌ Connection failed. Check your settings.")


def main():
    """Main execution flow."""
    print("\n" + "▓" * 60)
    print("  AGENT 5 — PHASE 1: BETFAIR SETUP")
    print("  SHADOW-DOMINION | DΞMON CORE v9999999 | BLACK CODE CURSE")
    print("▓" * 60)

    # Step 1: Check betfairlightweight
    print("\n[1/6] Checking betfairlightweight installation...")
    if not check_betfairlightweight():
        logger.error("Cannot proceed without betfairlightweight")
        return 1

    # Step 2: Generate SSL certificates
    print("\n[2/6] Generating SSL certificates...")
    certs = generate_ssl_certificate()
    logger.info(f"  Cert: {certs['cert']}")
    logger.info(f"  Key:  {certs['key']}")

    # Step 3: Print App Key guide
    print("\n[3/6] App Key registration guide...")
    guide = create_app_key_guide()
    print(guide)
    with open(CONFIG_DIR / 'APP_KEY_GUIDE.txt', 'w') as f:
        f.write(guide)
    logger.info(f"Guide saved to {CONFIG_DIR / 'APP_KEY_GUIDE.txt'}")

    # Step 4: Create trading config
    print("\n[4/6] Creating trading configuration...")
    trading = create_trading_config()
    with open(CONFIG_DIR / 'trading_config.json', 'w') as f:
        json.dump(trading, f, indent=2)
    logger.info(f"Trading config saved")

    # Step 5: Load existing config
    print("\n[5/6] Loading existing configuration...")
    config = load_config()
    if not config.get("app_key"):
        logger.warning("⚠️ No App Key configured. Run interactive setup or edit betfair_config.json")
        config["cert_path"] = certs["cert"]
        config["cert_key_path"] = certs["key"]
        save_config(config)
    else:
        logger.info(f"  App Key: {config['app_key'][:8]}...{config['app_key'][-4:]}")
        config["cert_path"] = certs["cert"]
        config["cert_key_path"] = certs["key"]
        save_config(config)

    # Step 6: Test connection (if configured)
    print("\n[6/6] Testing connection (if credentials configured)...")
    if config.get("app_key") and config.get("username"):
        client = setup_betfair_client(config)
        if client:
            test_connection(client)

    print("\n" + "=" * 60)
    print("  BETFAIR SETUP COMPLETE")
    print("  Next step: Run agent5_betfair_test.py to verify connection")
    print("  Or run: python -c \"from agent5_betfair_setup import interactive_setup; interactive_setup()\"")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

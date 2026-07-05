#!/usr/bin/env python3
"""
Agent 5 — Phase 1b: BETFAIR CONNECTION TEST
=============================================
Tests the Betfair API connection with error diagnostics.
"""

import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('BetfairTest')

CONFIG_FILE = Path(__file__).parent / 'betfair_config' / 'betfair_config.json'


def main():
    print("\n" + "=" * 60)
    print("  BETFAIR API CONNECTION TEST")
    print("=" * 60)

    # Load config
    if not CONFIG_FILE.exists():
        logger.error(f"❌ Config file not found at {CONFIG_FILE}")
        logger.error("   Run agent5_betfair_setup.py first")
        return 1

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    missing = []
    if not config.get("username"): missing.append("username")
    if not config.get("password"): missing.append("password")
    if not config.get("app_key"): missing.append("app_key")

    if missing:
        logger.error(f"❌ Missing configuration: {', '.join(missing)}")
        logger.error("   Edit betfair_config.json or run interactive setup")
        return 1

    logger.info(f"📋 Configuration loaded:")
    logger.info(f"   Username: {config['username'][:3]}***")
    logger.info(f"   App Key:  {config['app_key'][:8]}...{config['app_key'][-4:]}")
    logger.info(f"   SSL:      {'Enabled' if config.get('use_ssl') else 'Disabled'}")
    logger.info(f"   Cert:     {config.get('cert_path', 'N/A')}")

    # Try importing betfairlightweight
    try:
        from betfairlightweight import APIClient
        logger.info("✅ betfairlightweight imported successfully")
    except ImportError as e:
        logger.error(f"❌ betfairlightweight import failed: {e}")
        logger.error("   Run: pip install betfairlightweight")
        return 1

    # Try SSL certs
    if config.get("use_ssl"):
        cert_path = config.get("cert_path", "")
        key_path = config.get("cert_key_path", "")
        if cert_path and key_path:
            if Path(cert_path).exists() and Path(key_path).exists():
                logger.info(f"✅ SSL certificates found")
            else:
                logger.warning(f"⚠️ SSL certificates not found at expected paths")
                logger.warning(f"   Cert: {cert_path} - exists: {Path(cert_path).exists()}")
                logger.warning(f"   Key:  {key_path} - exists: {Path(key_path).exists()}")
        else:
            logger.warning("⚠️ SSL configured but paths not set")

    # Initialize client
    try:
        client = APIClient(
            username=config["username"],
            password=config["password"],
            app_key=config["app_key"],
            cert_files=(
                config.get("cert_path"),
                config.get("cert_key_path")
            ) if config.get("use_ssl") and config.get("cert_path") else None,
            timeout=config.get("timeout", 30)
        )
        logger.info("✅ APIClient initialized")
    except Exception as e:
        logger.error(f"❌ APIClient initialization failed: {e}")
        return 1

    # Test login
    print("\n" + "-" * 40)
    print("  Testing login...")
    try:
        client.login()
        logger.info("✅✅✅ LOGIN SUCCESSFUL!")
        logger.info("   Session token obtained")
    except Exception as e:
        error_msg = str(e)
        if "CERTIFICATE_REQUIRED" in error_msg:
            logger.error("❌ SSL certificate required — upload your .crt to developer.betfair.com")
            logger.error("   Go to: developer.betfair.com → My Account → Certificates")
            logger.error("   Upload the certificate from your betfair_config/certs/ folder")
        elif "INVALID_USERNAME_OR_PASSWORD" in error_msg:
            logger.error("❌ Invalid username or password")
        elif "APP_KEY_INVALID" in error_msg or "APP_LIMIT_EXCEEDED" in error_msg:
            logger.error("❌ App Key invalid or expired")
            logger.error("   Check: developer.betfair.com → My Account → Applications")
        elif "TOO_MANY_REQUESTS" in error_msg:
            logger.error("❌ Too many requests — wait 60 seconds and try again")
        else:
            logger.error(f"❌ Login failed: {error_msg}")
        return 1

    # Test navigation
    print("\n  Testing navigation data...")
    try:
        events = client.navigation.navigation_data()
        logger.info(f"✅ Navigation data received: {type(events).__name__}")
        # Try to find football events
        if events and hasattr(events, 'children'):
            for child in events.children[:3]:
                logger.info(f"   Event type: {child.name}")
    except Exception as e:
        logger.warning(f"⚠️ Navigation data failed (non-fatal): {e}")

    # Test account
    print("\n  Testing account access...")
    try:
        details = client.account.get_account_details()
        logger.info(f"✅ Account details retrieved")
    except Exception as e:
        logger.warning(f"⚠️ Account details failed (non-fatal): {e}")

    print("\n" + "=" * 60)
    print("  ✅✅ TEST COMPLETE ✅✅")
    print("  Betfair API is configured and ready for use.")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

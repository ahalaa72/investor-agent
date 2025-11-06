#!/usr/bin/env python3
"""
Script to check if QUESTRADE_REFRESH_TOKEN environment variable is properly loaded.
"""

import os
import sys
from pathlib import Path

# Try to load from .env file
try:
    from dotenv import load_dotenv
    dotenv_available = True
except ImportError:
    dotenv_available = False

def check_env_file():
    """Check if .env file exists and contains QUESTRADE_REFRESH_TOKEN."""
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
        with open(env_file, 'r') as f:
            content = f.read()
            if 'QUESTRADE_REFRESH_TOKEN' in content:
                print("✅ QUESTRADE_REFRESH_TOKEN found in .env file")
                # Check if it's not the template value
                if 'your_questrade_refresh_token_here' in content:
                    print("⚠️  WARNING: .env file contains template value, not actual token")
                    return False
                return True
            else:
                print("❌ QUESTRADE_REFRESH_TOKEN NOT found in .env file")
                return False
    else:
        print("❌ .env file NOT found")
        print(f"   Expected location: {env_file.absolute()}")
        return False

def check_env_template():
    """Check if .env.template exists."""
    template_file = Path(".env.template")
    if template_file.exists():
        print(f"ℹ️  .env.template exists at: {template_file.absolute()}")
        print("   Copy it to .env and add your token:")
        print("   cp .env.template .env")
    else:
        print("⚠️  .env.template NOT found")

def check_environment_variable():
    """Check if QUESTRADE_REFRESH_TOKEN is set in environment."""
    token = os.getenv("QUESTRADE_REFRESH_TOKEN")
    if token:
        print("✅ QUESTRADE_REFRESH_TOKEN is set in environment")
        print(f"   Length: {len(token)} characters")
        if len(token) > 8:
            print(f"   Value: {token[:4]}...{token[-4:]}")
        else:
            print("   Value: *** (too short to display safely)")

        # Check if it's a template value
        if token == "your_questrade_refresh_token_here":
            print("⚠️  WARNING: Token is still the template placeholder!")
            return False
        return True
    else:
        print("❌ QUESTRADE_REFRESH_TOKEN is NOT set in environment")
        return False

def check_investor_agent_loading():
    """Check if investor_agent can load the token."""
    print("\n" + "="*60)
    print("Testing investor_agent module loading...")
    print("="*60)

    try:
        # Add current directory to path
        sys.path.insert(0, str(Path(__file__).parent))

        # Load dotenv if available
        if dotenv_available:
            load_dotenv()
            print("✅ python-dotenv loaded")

        # Try to import the questrade module
        try:
            from investor_agent.questrade import _questrade_available, get_questrade_client

            if _questrade_available:
                print("✅ questrade-api package is installed")
                print("✅ Questrade module loaded successfully")

                # Try to create client
                try:
                    client = get_questrade_client()
                    print("✅ QuestradeClient initialized successfully")
                    return True
                except ValueError as e:
                    print(f"❌ Failed to initialize QuestradeClient: {e}")
                    return False
                except Exception as e:
                    print(f"❌ Error initializing QuestradeClient: {e}")
                    return False
            else:
                print("❌ questrade-api package is NOT installed")
                print("   Install with: uv sync --extra questrade")
                return False

        except ImportError as e:
            print(f"❌ Failed to import questrade module: {e}")
            return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    print("="*60)
    print("  QUESTRADE ENVIRONMENT VARIABLE CHECKER")
    print("="*60)
    print()

    print("1. Checking .env file...")
    print("-"*60)
    has_env_file = check_env_file()
    print()

    print("2. Checking environment variable...")
    print("-"*60)
    has_env_var = check_environment_variable()
    print()

    print("3. Checking .env.template...")
    print("-"*60)
    check_env_template()
    print()

    print("4. Checking investor_agent module...")
    print("-"*60)
    module_ok = check_investor_agent_loading()
    print()

    # Summary
    print("="*60)
    print("  SUMMARY")
    print("="*60)

    all_ok = has_env_var and module_ok

    if all_ok:
        print("✅ Everything is configured correctly!")
        print("   You can now use the Questrade tools.")
    else:
        print("❌ Configuration incomplete. Follow these steps:")
        print()
        print("STEP 1: Create .env file")
        print("   cp .env.template .env")
        print()
        print("STEP 2: Get your Questrade refresh token")
        print("   Visit: https://www.questrade.com/api/")
        print("   Follow 'Getting Started' to generate a token")
        print()
        print("STEP 3: Add token to .env file")
        print("   Edit .env and set:")
        print("   QUESTRADE_REFRESH_TOKEN=your_actual_token_here")
        print()
        print("STEP 4: Install questrade-api (if not installed)")
        print("   uv sync --extra questrade")
        print()
        print("STEP 5: Test again")
        print("   python check_questrade_env.py")

    print("="*60)

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())

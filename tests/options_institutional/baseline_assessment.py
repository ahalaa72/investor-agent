#!/usr/bin/env python3
"""
Baseline Capabilities Assessment

Documents the current state of options analysis BEFORE institutional upgrade.
Generates evidence to compare against post-upgrade improvements.
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def check_feature(name, check_fn, description=""):
    """Check if a feature exists and works"""
    try:
        result = check_fn()
        status = "✅" if result else "❌"
        print(f"{status} {name:40} {description}")
        return result
    except Exception as e:
        print(f"❌ {name:40} Error: {str(e)[:30]}")
        return False


def assess_current_capabilities():
    """Assess all current options capabilities"""
    print_header("BASELINE CAPABILITIES ASSESSMENT")
    print(f"{Colors.OKCYAN}Testing current options analysis capabilities...{Colors.ENDC}\n")

    capabilities = {}

    # Test 1: Basic Options Tools
    print(f"{Colors.BOLD}Phase 1: Core Options Tools{Colors.ENDC}")

    def check_analyze_options_mcmillan():
        from investor_agent.server import analyze_options_mcmillan
        return callable(analyze_options_mcmillan)

    capabilities['analyze_options_mcmillan'] = check_feature(
        "analyze_options_mcmillan",
        check_analyze_options_mcmillan,
        "Core McMillan analysis"
    )

    def check_generate_options_trade_plan():
        from investor_agent.server import generate_options_trade_plan
        return callable(generate_options_trade_plan)

    capabilities['generate_options_trade_plan'] = check_feature(
        "generate_options_trade_plan",
        check_generate_options_trade_plan,
        "Trade plan generator"
    )

    # Test 2: Strategy Construction
    print(f"\n{Colors.BOLD}Phase 2: Strategy Construction{Colors.ENDC}")

    def check_explicit_legs():
        from investor_agent.server import generate_options_trade_plan
        try:
            result = generate_options_trade_plan('SPY', 'LONG', 10000, 45)
            has_legs = 'legs' in result.get('options_plan', {}).get('entry', {})
            if has_legs:
                num_legs = len(result['options_plan']['entry']['legs'])
                print(f"       Found {num_legs} explicit legs in strategy")
            return has_legs
        except:
            return False

    capabilities['explicit_strategy_construction'] = check_feature(
        "Explicit Strategy Construction",
        check_explicit_legs,
        "4-leg trades with strikes/premiums"
    )

    def check_position_greeks():
        from investor_agent.server import generate_options_trade_plan
        try:
            result = generate_options_trade_plan('SPY', 'LONG', 10000, 45)
            has_greeks = 'position_delta' in result.get('options_plan', {}).get('greeks', {})
            return has_greeks
        except:
            return False

    capabilities['position_greeks'] = check_feature(
        "Position Greeks Aggregation",
        check_position_greeks,
        "Delta, Theta for full position"
    )

    # Test 3: Institutional Features (Expected to be missing)
    print(f"\n{Colors.BOLD}Phase 3: Institutional Features (Upgrade Targets){Colors.ENDC}")

    def check_iv_skew():
        try:
            from investor_agent.server import analyze_iv_skew
            return callable(analyze_iv_skew)
        except:
            return False

    capabilities['iv_skew_analysis'] = check_feature(
        "IV Skew Analysis",
        check_iv_skew,
        "Put IV vs Call IV"
    )

    def check_term_structure():
        try:
            from investor_agent.server import analyze_iv_term_structure
            return callable(analyze_iv_term_structure)
        except:
            return False

    capabilities['term_structure_analysis'] = check_feature(
        "Term Structure Analysis",
        check_term_structure,
        "Contango/Backwardation"
    )

    def check_vanna():
        try:
            from investor_agent.server import calculate_vanna
            return callable(calculate_vanna)
        except:
            return False

    capabilities['vanna_calculation'] = check_feature(
        "Vanna (∂Delta/∂IV)",
        check_vanna,
        "IV sensitivity of delta"
    )

    def check_charm():
        try:
            from investor_agent.server import calculate_charm
            return callable(calculate_charm)
        except:
            return False

    capabilities['charm_calculation'] = check_feature(
        "Charm (∂Delta/∂Time)",
        check_charm,
        "Time decay of delta"
    )

    def check_gex():
        try:
            from investor_agent.server import analyze_gamma_exposure
            return callable(analyze_gamma_exposure)
        except:
            return False

    capabilities['gamma_exposure_analysis'] = check_feature(
        "Gamma Exposure (GEX)",
        check_gex,
        "Dealer positioning"
    )

    def check_beta_weighted():
        try:
            from investor_agent.server import calculate_portfolio_beta_weighted_delta
            return callable(calculate_portfolio_beta_weighted_delta)
        except:
            return False

    capabilities['beta_weighted_delta'] = check_feature(
        "Beta-Weighted Delta",
        check_beta_weighted,
        "SPY-normalized exposure"
    )

    def check_concentration():
        try:
            from investor_agent.server import check_portfolio_concentration_limits
            return callable(check_portfolio_concentration_limits)
        except:
            return False

    capabilities['concentration_limits'] = check_feature(
        "Concentration Limits",
        check_concentration,
        "Ticker/Sector/Expiration limits"
    )

    def check_var():
        try:
            from investor_agent.server import calculate_portfolio_var
            return callable(calculate_portfolio_var)
        except:
            return False

    capabilities['var_calculation'] = check_feature(
        "VaR/CVaR Calculation",
        check_var,
        "Value at Risk metrics"
    )

    # Generate Score
    print_header("ASSESSMENT SUMMARY")

    total_features = len(capabilities)
    working_features = sum(capabilities.values())
    completion_pct = (working_features / total_features) * 100

    print(f"{Colors.OKGREEN}Working Features: {working_features}/{total_features}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}Completion: {completion_pct:.1f}%{Colors.ENDC}\n")

    # Identify gaps
    print(f"{Colors.WARNING}Features to Implement:{Colors.ENDC}")
    missing = [name for name, status in capabilities.items() if not status]
    for feature in missing:
        print(f"  ⏸️  {feature}")

    # Generate detailed evidence report
    evidence = {
        "assessment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "capabilities": capabilities,
        "summary": {
            "total_features": total_features,
            "working_features": working_features,
            "missing_features": len(missing),
            "completion_percentage": round(completion_pct, 1)
        },
        "missing_features": missing,
        "institutional_gap": {
            "iv_surface_analysis": not (capabilities.get('iv_skew_analysis') and capabilities.get('term_structure_analysis')),
            "advanced_greeks": not (capabilities.get('vanna_calculation') and capabilities.get('charm_calculation') and capabilities.get('gamma_exposure_analysis')),
            "portfolio_risk": not (capabilities.get('beta_weighted_delta') and capabilities.get('concentration_limits') and capabilities.get('var_calculation'))
        }
    }

    # Save evidence
    output_file = Path(__file__).parent / "baseline_evidence.json"
    with open(output_file, 'w') as f:
        json.dump(evidence, f, indent=2)

    print(f"\n{Colors.OKGREEN}✅ Evidence saved to: {output_file}{Colors.ENDC}")

    # Test actual functionality
    print_header("FUNCTIONAL TESTING")
    test_actual_output()

    return evidence


def test_actual_output():
    """Test actual output from generate_options_trade_plan"""
    print(f"{Colors.OKCYAN}Testing actual SPY options trade plan...{Colors.ENDC}\n")

    try:
        from investor_agent.server import generate_options_trade_plan

        result = generate_options_trade_plan('SPY', 'LONG', 10000, 45)

        print(f"{Colors.BOLD}Current Output Structure:{Colors.ENDC}")
        print(f"  Ticker: {result.get('ticker')}")
        print(f"  Direction: {result.get('direction')}")
        print(f"  Current Price: ${result.get('current_price'):.2f}")

        plan = result.get('options_plan', {})
        print(f"\n{Colors.BOLD}Options Plan:{Colors.ENDC}")
        print(f"  Status: {plan.get('status')}")
        print(f"  Strategy: {plan.get('strategy')}")

        if 'entry' in plan and 'legs' in plan['entry']:
            legs = plan['entry']['legs']
            print(f"\n{Colors.OKGREEN}  ✅ Explicit Legs Defined: {len(legs)}{Colors.ENDC}")
            for i, leg in enumerate(legs, 1):
                print(f"    Leg {i}: {leg.get('action')} {leg.get('option_type')} @ ${leg.get('strike')}")
        else:
            print(f"\n{Colors.WARNING}  ⚠️  No explicit legs (strategy name only){Colors.ENDC}")

        if 'greeks' in plan:
            greeks = plan['greeks']
            print(f"\n{Colors.BOLD}Position Greeks:{Colors.ENDC}")
            print(f"  Delta: {greeks.get('position_delta', 'N/A')}")
            print(f"  Theta: {greeks.get('position_theta', 'N/A')}")
        else:
            print(f"\n{Colors.WARNING}  ⚠️  No position Greeks calculated{Colors.ENDC}")

        print(f"\n{Colors.OKGREEN}✅ Functional test complete{Colors.ENDC}")

    except Exception as e:
        print(f"{Colors.FAIL}❌ Error testing trade plan: {e}{Colors.ENDC}")


if __name__ == "__main__":
    try:
        evidence = assess_current_capabilities()

        print_header("NEXT STEPS")
        print(f"{Colors.OKCYAN}Implementation Priority:{Colors.ENDC}\n")
        print(f"1. Phase 1: IV Skew + Term Structure + Explicit Construction")
        print(f"2. Phase 2: Vanna + Charm + GEX")
        print(f"3. Phase 3: Beta-Weighted Delta + Concentration + VaR")
        print(f"4. Phase 4: Advanced Strategies (Calendars, Jade Lizards, Ratios)\n")

        print(f"{Colors.BOLD}Expected Impact:{Colors.ENDC}")
        print(f"  • +20-30% strategy selection improvement (IV skew)")
        print(f"  • +80% actionability (explicit construction)")
        print(f"  • Institutional-grade risk management (portfolio Greeks)\n")

    except Exception as e:
        print(f"{Colors.FAIL}Error during assessment: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

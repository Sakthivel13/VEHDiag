"""Development Runner."""
import argparse


def run_benchmark():
    from benchmarks.benchmarks import run_pipeline_benchmark
    run_pipeline_benchmark()


def simulate_traffic():
    print("Simulating CAN traffic (scaffold)")


def run_discovery_offline():
    from discovery.discovery import DiscoveryEngine
    eng = DiscoveryEngine({})
    print(f"Discovery result: {eng.run([])}")


def main():
    parser = argparse.ArgumentParser(description="Development utilities")
    parser.add_argument("--benchmark", action="store_true", help="Run pipeline benchmark")
    parser.add_argument("--simulate", action="store_true", help="Simulate CAN traffic")
    parser.add_argument("--discovery", action="store_true", help="Run discovery offline")

    args = parser.parse_args()

    if args.benchmark:
        run_benchmark()
    elif args.simulate:
        simulate_traffic()
    elif args.discovery:
        run_discovery_offline()
    else:
        print("Use --benchmark, --simulate, or --discovery")


if __name__ == "__main__":
    main()
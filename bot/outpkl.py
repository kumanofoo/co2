from co2.co2plot import get_latest
import pickle
import argparse
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Save pickle of get_latest's result for tests"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Axes configuration"
    )
    parser.add_argument(
        "-o", "--output",
        default="co2now_result.pkl",
        help="get_latest result pickle"
    )
    args = parser.parse_args()

    now = get_latest(config=args.config)
    pklfile = open(args.output, "wb")
    pickle.dump(now, pklfile)
    pklfile.close()
    print("# show dumped get_latest results in JSON")
    print(json.dumps(now, indent=2, sort_keys=True))

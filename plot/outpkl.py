from co2plot import co2now
import pickle
import sys
import argparse
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save pickle of co2now's result for tests")
    parser.add_argument("-c", "--config", default="config.json", help="Axes configuration")
    parser.add_argument("-o", "--output", default="co2now_result.pkl", help="co2now result pickle")
    args = parser.parse_args()

    now = co2now(config=args.config)
    pklfile = open(args.output, "wb")
    pickle.dump(now, pklfile)
    pklfile.close()
    print("# show dumped co2now results in JSON")
    print(json.dumps(now, indent=2, sort_keys=True))
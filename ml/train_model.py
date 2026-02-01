from AiOrderFilter import AiOrderFilter
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
        ai = AiOrderFilter() # Path will be auto-generated from CSV name
        ai.train(csv_file)
    else:
        print("Usage: python train_model.py data.csv")
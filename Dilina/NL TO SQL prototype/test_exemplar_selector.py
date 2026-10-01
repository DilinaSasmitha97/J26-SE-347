import time
from exemplar_selector import exemplar_selector

def test():
    test_queries = [
        "What is the maximum capacity and the average of all stadiums ?",
        "Find the names of properties that are either houses or apartments with more than 1 room?",
        "Which car makers produce at least 2 models and more than 3 cars?",
        "What country is Jetblue Airways affiliated with?"
    ]

    for q in test_queries:
        t0 = time.perf_counter()
        exemplars = exemplar_selector.retrieve(q, k=2)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        print("=" * 70)
        print(f"QUERY: {q}")
        print(f"Retrieval Latency: {elapsed_ms:.2f}ms | Matches Found: {len(exemplars)}")
        formatted = exemplar_selector.format_exemplars(exemplars)
        print(formatted)
        print()

if __name__ == "__main__":
    test()

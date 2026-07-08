"""Put the project root on sys.path so tests can import data/ and engine/."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

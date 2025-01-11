import time
import unittest
from django.test import TestCase
from django.db import connections, OperationalError, ProgrammingError
from django.core.management import call_command
from django.conf import settings
from gbp_django.utils.model_interface import GroqModel, OllamaModel


class ModelBenchmarkTests(TestCase):
    def _database_exists(self, database_name):
        """Check if a database exists."""
        connection = connections['default']
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname='{database_name}'")
            return bool(cursor.fetchone())
        except OperationalError:
            return False

    def _extension_exists(self, extension_name):
        """Check if a database extension exists."""
        connection = connections['default']
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT 1 FROM pg_extension WHERE extname='{extension_name}'")
            return bool(cursor.fetchone())
        except ProgrammingError:
            return False

    def _create_vector_extension(self):
        """Create the vector extension if it does not exist."""
        connection = connections['default']
        cursor = connection.cursor()
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            connection.commit()
            print("Vector extension successfully installed.")
        except Exception as e:
            print(f"Error installing vector extension: {e}")

    def setUp(self):
        self.test_queries = [
            "What are the key features of your business automation platform?",
            "How do I verify my business profile?",
            "Can you help me optimize my business listing?",
            "What's the best way to respond to customer reviews?",
            "How can I improve my local SEO ranking?"
        ]

        self.test_context = """
        GBP Automation Pro is a comprehensive platform for managing Google Business Profiles.
        Key features include automated post creation, review management, and Q&A handling.
        The platform supports business verification, profile optimization, and local SEO enhancement.
        """

        self.models = {
            'groq': GroqModel(),
            'ollama': OllamaModel()
        }

        # Ensure the vector extension is installed
        if not self._extension_exists('vector'):
            self._create_vector_extension()

    def test_response_generation_benchmark(self):
        results = {}

        for model_name, model in self.models.items():
            start_time = time.time()
            responses = []

            for query in self.test_queries:
                try:
                    response = model.generate_response(query, self.test_context)
                    responses.append({
                        'query': query,
                        'response': response,
                        'success': bool(response and len(response) > 0)
                    })
                except Exception as e:
                    responses.append({
                        'query': query,
                        'error': str(e),
                        'success': False
                    })

            end_time = time.time()

            results[model_name] = {
                'total_time': end_time - start_time,
                'avg_time': (end_time - start_time) / len(self.test_queries),
                'success_rate': len([r for r in responses if r['success']]) / len(responses),
                'responses': responses
            }

        print("\n=== Model Benchmark Results ===")
        for model_name, result in results.items():
            print(f"\n{model_name.upper()} Results:")
            print(f"Total Time: {result['total_time']:.2f} seconds")
            print(f"Average Time per Query: {result['avg_time']:.2f} seconds")
            print(f"Success Rate: {result['success_rate'] * 100:.1f}%")

        for model_name, result in results.items():
            self.assertGreater(result['success_rate'], 0.5,
                               f"{model_name} success rate below 50%")
            self.assertLess(result['avg_time'], 30.0,
                            f"{model_name} average response time exceeds 30 seconds")

    def test_embedding_generation_benchmark(self):
        test_texts = [
            "Short business description",
            "Medium length business profile with some details about services and location",
            "A longer business description with multiple paragraphs discussing various aspects..."
        ]

        results = {}

        for model_name, model in self.models.items():
            start_time = time.time()
            embeddings = []

            for text in test_texts:
                try:
                    embedding = model.generate_embedding(text)
                    embeddings.append({
                        'text': text,
                        'embedding_size': len(embedding) if embedding else 0,
                        'success': bool(embedding and len(embedding) == 1536)
                    })
                except Exception as e:
                    embeddings.append({
                        'text': text,
                        'error': str(e),
                        'success': False
                    })

            end_time = time.time()

            results[model_name] = {
                'total_time': end_time - start_time,
                'avg_time': (end_time - start_time) / len(test_texts),
                'success_rate': len([e for e in embeddings if e['success']]) / len(embeddings),
                'embeddings': embeddings
            }

        print("\n=== Embedding Benchmark Results ===")
        for model_name, result in results.items():
            print(f"\n{model_name.upper()} Embedding Results:")
            print(f"Total Time: {result['total_time']:.2f} seconds")
            print(f"Average Time per Text: {result['avg_time']:.2f} seconds")
            print(f"Success Rate: {result['success_rate'] * 100:.1f}%")

        for model_name, result in results.items():
            self.assertGreater(result['success_rate'], 0.5,
                               f"{model_name} embedding success rate below 50%")
            self.assertLess(result['avg_time'], 10.0,
                            f"{model_name} average embedding time exceeds 10 seconds")

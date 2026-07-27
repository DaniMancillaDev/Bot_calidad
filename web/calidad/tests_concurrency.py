import concurrent.futures
from django.test import TransactionTestCase
from calidad.models import GlobalCounter
from shared.infrastructure.database.django_contador_repository import DjangoContadorRepository

class GlobalCounterConcurrencyTest(TransactionTestCase):
    
    def test_global_counter_concurrency(self):
        """
        Simula 50 operadores pidiendo entre 1 y 10 números de forma concurrente,
        y 2 importaciones web pidiendo 500 números simultáneamente.
        Valida que la transacción atómica (select_for_update) impida colisiones.
        """
        # Inicializamos el contador o lo obtenemos si ya fue creado por migración
        counter, _ = GlobalCounter.objects.get_or_create(nombre='fotos', defaults={'valor_actual': 1})
        valor_inicial = counter.valor_actual
        
        repo = DjangoContadorRepository()
        resultados = []
        
        def simulate_operator():
            import random
            n = random.randint(1, 10)
            return repo.obtener_y_avanzar_lote(user_id=1, n=n)

        def simulate_web_import():
            return repo.obtener_y_avanzar_lote(user_id=2, n=500)

        # Usamos 10 workers (Postgres puede tener limite de conexiones, así que 10 es seguro para tests locales)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures_ops = [executor.submit(simulate_operator) for _ in range(50)]
            futures_web = [executor.submit(simulate_web_import) for _ in range(2)]
            
            for future in concurrent.futures.as_completed(futures_ops + futures_web):
                resultados.extend(future.result())
                
        # Validaciones
        unicos = set(resultados)
        
        # Regla 1: Ningún ID debe repetirse
        self.assertEqual(len(unicos), len(resultados), "Hubo colisiones de contadores")
        
        # Regla 2: El total debe coincidir
        total_solicitado = len(resultados)
        counter = GlobalCounter.objects.get(nombre='fotos')
        
        self.assertEqual(counter.valor_actual, valor_inicial + total_solicitado)

    def test_pool_concurrency(self):
        """
        Escenario concurrente:
        GlobalCounter = 100
        NumeroReutilizable = [50]
        Dos operadores solicitan lote simultáneamente.
        Debe garantizarse que uno recibe el 50, y el otro no colisiona.
        """
        from calidad.models import NumeroReutilizable
        
        counter, _ = GlobalCounter.objects.get_or_create(nombre='fotos', defaults={'valor_actual': 100})
        counter.valor_actual = 100
        counter.save(update_fields=['valor_actual'])
        
        NumeroReutilizable.objects.create(numero=50)
        
        repo = DjangoContadorRepository()
        
        def simulate_operator():
            return repo.obtener_y_avanzar_lote(user_id=1, n=1)
            
        resultados = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(simulate_operator) for _ in range(2)]
            for future in concurrent.futures.as_completed(futures):
                resultados.extend(future.result())
                
        # Uno recibió el 50, el otro el 100
        self.assertCountEqual(resultados, [50, 100])
        # El contador global debe haber avanzado 1 posición a 101
        counter.refresh_from_db()
        self.assertEqual(counter.valor_actual, 101)
        self.assertEqual(NumeroReutilizable.objects.count(), 0)

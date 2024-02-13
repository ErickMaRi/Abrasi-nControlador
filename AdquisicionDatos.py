from typing import List, Tuple, Union
import random
import serial
from collections import deque
import numpy as np
from scipy.signal import lti
from scipy.signal import lsim
from scipy.signal import lfilter
from scipy.signal import butter

# Definición de funciones para la señal cuadrada y respuestas de sistemas de segundo orden

def square_wave(t, freq, amp):
    return amp * np.sign(np.sin(2 * np.pi * freq * t))

def system_response(t, input, natural_freq, damping_ratio, Kp, tau_s, theta_p):
    num = [Kp * natural_freq**2]
    den = [tau_s**2, 2 * damping_ratio * natural_freq * tau_s, natural_freq**2]
    system = lti(num, den)
    _, y, _ = lsim(system, input, t)  # Discard unwanted values with underscores
    return y

class Sensor:

    """
        Inicializa un objeto Sensor con el tipo de sensor y el desvío estándar del ruido.

        Args:
        - tipo_sensor (str): El tipo de sensor (por ejemplo, "termocupla", "resistencia", "superficie").
        - ruido_std (float): El desvío estándar del ruido para el sensor.

        Raises:
        - ValueError: Si el tipo de sensor no es válido.
    """
    
    def __init__(self, tipo_sensor, ruido_std):
        self.tipo_sensor = tipo_sensor
        self.ruido_std = ruido_std
        self.valor_actual = 0

    def generar_dato(self):
        """
        Genera un dato simulado para el sensor y agrega ruido.

        Returns:
        - float: El dato simulado del sensor con ruido.
        """
        if self.tipo_sensor == "termocupla":
            # Simular la dinámica de la termocupla
            ...
        elif self.tipo_sensor == "resistencia":
            # Simular la relación temperatura-resistencia
            ...
        elif self.tipo_sensor == "superficie":
            # Modelar la transferencia de calor y la respuesta térmica
            ...
        else:
            raise ValueError("Tipo de sensor no válido")

        valor_simulado = self.valor_actual + np.random.normal(0, self.ruido_std)
        self.valor_actual = valor_simulado

        return valor_simulado

class ArduinoMock:
    """
        Inicializa un objeto ArduinoMock para simular la adquisición de datos desde Arduino.

        Args:
        - frecuencia_muestreo (float): La frecuencia de muestreo de los datos.
        - numero_muestras (int): El número de muestras a generar.
        - params (dict): Parámetros para la simulación de los sensores.

        Atributos:
        - frecuencia_muestreo (float): La frecuencia de muestreo de los datos.
        - numero_muestras (int): El número de muestras a generar.
        - params (dict): Parámetros para la simulación de los sensores.
        - sensores (dict): Diccionario que contiene los sensores simulados y sus parámetros.
    """
    def __init__(self, frecuencia_muestreo, numero_muestras, params):
        self.frecuencia_muestreo = frecuencia_muestreo
        self.numero_muestras = numero_muestras
        self.params = params
        self.sensores = {
            "termocupla": {"sensor": Sensor("termocupla", 0.01), "params": params["termocupla"]},
            "resistencia": {"sensor": Sensor("resistencia", 0.02), "params": params["resistencia"]},
            "superficie": {"sensor": Sensor("superficie", 0.03), "params": params["superficie"]},
        }

    def generar_datos(self):
        """
        Genera datos simulados para todos los sensores.

        Returns:
        - np.ndarray: Datos simulados para todos los sensores.
        """

        # Generar tiempo de simulación
        time = np.linspace(0, 100, self.numero_muestras)  # Ajustar la duración según sea necesario

        # Generar señal cuadrada de baja frecuencia para la entrada
        square_wave_freq = 0.2  # Frecuencia baja
        square_wave_amp = 1  # Amplitud ajustable según necesidades
        square_wave_input = square_wave(time, square_wave_freq, square_wave_amp)

        # Inicializar array para almacenar datos de los sensores
        datos = np.zeros((self.numero_muestras, len(self.sensores) + 1))

        # Generar datos simulados para cada sensor y agregar ruido
        for i, (sensor_name, sensor_data) in enumerate(self.sensores.items()):
            sensor = sensor_data["sensor"]
            params = sensor_data["params"]
            datos[:, i] = system_response(time, square_wave_input, params["natural_freq"], 
                                        params["damping_ratio"], params["Kp"], params["tau_s"], params["theta_p"])

        # Agregar la señal cuadrada en la última columna
        datos[:, -1] = square_wave_input
        return datos

class AdquisicionDatos:
    """
        Inicializa un objeto AdquisicionDatos para adquirir y filtrar datos desde un dispositivo.

        Args:
        - puerto_serial (str): El puerto serial para la comunicación.
        - baudios (int): La velocidad de baudios para la comunicación serial.
        - frecuencia_muestreo (float): La frecuencia de muestreo de los datos.
        - tipo_filtro (str): El tipo de filtro a aplicar.
        - tamanio_cache (int): El tamaño de la caché para almacenar datos.
        - MOCK (bool): Indica si se está utilizando un entorno de simulación.
        - puerto_virtual (bool, opcional): Indica si se está utilizando un puerto serial virtual.
    """
    def __init__(self,
                 puerto_serial: str,
                 baudios: int,
                 frecuencia_muestreo: float,
                 tipo_filtro: str,
                 tamanio_cache: int,
                 MOCK: bool,
                 puerto_virtual: bool = False):

        self.tamanio_cache = tamanio_cache
        self.puerto_serial = puerto_serial
        self.baudios = baudios
        self.frecuencia_muestreo = frecuencia_muestreo
        self._serial = None
        self._cache = np.zeros((tamanio_cache, 4))
        self.MOCK = MOCK
        self.puerto_virtual = puerto_virtual
        self.tipo_filtro = tipo_filtro
        self.numero_muestras = 10000
        self.params = {
            "termocupla": {"natural_freq": 10, "damping_ratio": 0.5, "Kp": 1.0, "tau_s": 1.0, "theta_p": 0.0},
            "resistencia": {"natural_freq": 20, "damping_ratio": 0.6, "Kp": 2.0, "tau_s": 1.0, "theta_p": 0.0},
            "superficie": {"natural_freq": 30, "damping_ratio": 0.7, "Kp": 0.5, "tau_s": 1.0, "theta_p": 0.0}
        }

        if not self.MOCK:
            self._serial = serial.Serial(self.puerto_serial, self.baudios)

    def leer_datos(self, datos_mock=None) -> Union[List[float], None]:
        """
        Lee los datos del dispositivo, ya sea desde un entorno real o simulado.

        Returns:
        - Union[List[float], None]: Los datos leídos del dispositivo o None si hay un error.
        """

        def _leer_datos_mock(self):
            arduino_mock = ArduinoMock(self.frecuencia_muestreo, self.numero_muestras, self.params)
            datos = arduino_mock.generar_datos()
            return datos

        return _leer_datos_mock(self) if self.MOCK else self._leer_datos_real(datos_mock)

    def _leer_datos_real(self):
        """
        Lee los datos del dispositivo en un entorno real.

        Returns:
        - List[float]: Los datos leídos del dispositivo.
        """
        self._abrir_puerto_serial()
        datos = self._serial.readline().decode("utf-8").strip()
        datos = [float(valor) for valor in datos.split(",")]
        return datos

    def aplicar_filtro_digital(self, datos: List[float]) -> Union[List[float], None]:
        """
        Aplica un filtro digital a los datos.

        Args:
        - datos (List[float]): Los datos a filtrar.

        Returns:
        - Union[List[float], None]: Los datos filtrados o None si el tipo de filtro no es válido.
        """

        if self.tipo_filtro == "promedio":
            return [sum(datos[i:i + 10]) / 10 for i in range(0, len(datos), 10)]
        elif self.tipo_filtro == "pasos_bajos":
            frecuencia_corte = 10
            orden = 4
            b, a = butter(orden, frecuencia_corte, btype="low", fs=self.frecuencia_muestreo)
            datos_filtrados = lfilter(b, a, datos)
            return datos_filtrados
        else:
            raise ValueError("Tipo de filtro no válido")

    def almacenar_en_cache(self, datos: np.ndarray):
        """
        Almacena datos en la caché.

        Args:
        - datos (np.ndarray): Los datos a almacenar en la caché.
        """
        try:
            if len(datos) != self.tamanio_cache:
                datos = datos[:self.tamanio_cache]

            if datos.shape[1] != 4:
                raise ValueError("Los datos no tienen la forma correcta (número_muestras, 4)")

            self._cache = np.roll(self._cache, -len(datos), axis=0)
            self._cache[-len(datos):] = datos
        except ValueError as e:
            print(f"Error al almacenar en caché: {e}")
            if len(datos) > self.tamanio_cache:
                print(f"Reduciendo tamaño de datos a {self.tamanio_cache} entradas")
                datos = datos[:self.tamanio_cache]
                self._cache = np.roll(self._cache, -len(datos), axis=0)
                self._cache[-len(datos):] = datos

    def obtener_datos_cache(self) -> np.ndarray:
        """
        Obtiene los datos almacenados en la caché.

        Returns:
        - np.ndarray: Los datos almacenados en la caché.
        """
        return np.copy(self._cache)
    
def main():
    import numpy as np
    import matplotlib.pyplot as plt

    # Parámetros de configuración
    puerto_serial = "/dev/ttyACM0"
    baudios = 9600
    frecuencia_muestreo = 10
    tipo_filtro = "promedio"
    tamanio_cache = 100
    MOCK = True
    puerto_virtual = True

    try:
        # Creación del módulo de adquisición de datos
        adquisicion_datos = AdquisicionDatos(
            puerto_serial, baudios, frecuencia_muestreo, tipo_filtro, tamanio_cache, MOCK, puerto_virtual
        )

        # Simulación de la lectura de datos
        datos_sin_filtro = adquisicion_datos.leer_datos()

        if datos_sin_filtro is not None:
            datos_filtrados = adquisicion_datos.aplicar_filtro_digital(datos_sin_filtro)
            print(datos_sin_filtro[:, 0])
            print(datos_sin_filtro[:, 1])
            print(datos_sin_filtro[:, 2])
            print(datos_sin_filtro[:, 3])
        else:
            datos_filtrados = None

        if datos_filtrados is not None:
            datos_filtrados_array = np.array(datos_filtrados)
            adquisicion_datos.almacenar_en_cache(datos_filtrados_array)

        # Obtención de datos de la caché
        datos_cache = adquisicion_datos.obtener_datos_cache()

        if datos_cache is not None:
            # Extracción de las variables de interés
            acciones = datos_cache[:, 3]
            temperaturas1 = datos_cache[:, 0]
            temperaturas2 = datos_cache[:, 1]
            temperaturas3 = datos_cache[:, 2]

            # Generación del primer gráfico
            plt.figure(figsize=(10, 6))
            plt.plot(acciones, temperaturas1, label="Temperatura 1")
            plt.plot(acciones, temperaturas2, label="Temperatura 2")
            plt.plot(acciones, temperaturas3, label="Temperatura 3")
            plt.xlabel("Acción del controlador")
            plt.ylabel("Temperatura")
            plt.legend()
            plt.title("Respuestas sensoriales en función de la acción del controlador")
            plt.show()

            # Generación del segundo gráfico
            plt.figure(figsize=(10, 6))
            time_seconds = np.arange(len(acciones))
            plt.plot(time_seconds, acciones, label="Acción del controlador")
            plt.plot(time_seconds, temperaturas1, label="Temperatura 1")
            plt.plot(time_seconds, temperaturas2, label="Temperatura 2")
            plt.plot(time_seconds, temperaturas3, label="Temperatura 3")
            plt.xlabel("Tiempo (segundos)")
            plt.ylabel("Valores")
            plt.legend()
            plt.title("Respuestas sensoriales y acción del controlador segundo a segundo")
            plt.show()

            # Impresión de información
            print("---- Datos sin filtro ----")
            print(f"Datos: {datos_sin_filtro}")
            print(f"Tamaño: {datos_sin_filtro.__sizeof__()}")

            print("---- Datos con filtro ----")
            print(f"Datos: {datos_filtrados}")
            print(f"Tamaño: {datos_filtrados.__sizeof__()}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

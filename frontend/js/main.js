document.addEventListener("DOMContentLoaded", () => {
    const API_URL = 'https://api-libros-7k6t.onrender.com';
    let chartInstance = null;
    let datosGlobales = {};
    let fechasGlobales = [];

    // Formateador de moneda chilena
    const formatearDinero = (monto) => {
        return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(monto);
    };

    fetch(API_URL)
        .then(response => response.json())
        .then(data => {
            const historial = data.historial;
            
            fechasGlobales = [...new Set(historial.map(item => item.fecha))];
            
            // Agrupar datos
            historial.forEach(item => {
                if (!datosGlobales[item.titulo]) {
                    datosGlobales[item.titulo] = { precios: {}, max: 0, min: Infinity };
                }
                const precio = item.precio;
                datosGlobales[item.titulo].precios[item.fecha] = precio;
                
                // Calcular mínimo y máximo histórico sobre la marcha
                if (precio < datosGlobales[item.titulo].min) datosGlobales[item.titulo].min = precio;
                if (precio > datosGlobales[item.titulo].max) datosGlobales[item.titulo].max = precio;
            });

            poblarFiltro();
            actualizarDashboard("Todos"); // Inicia mostrando todo

            // Evento para cuando cambies de libro en el menú
            document.getElementById('filtroLibro').addEventListener('change', (e) => {
                actualizarDashboard(e.target.value);
            });
        })
        .catch(error => console.error("Error al cargar:", error));

    function poblarFiltro() {
        const select = document.getElementById('filtroLibro');
        Object.keys(datosGlobales).forEach(titulo => {
            const option = document.createElement('option');
            option.value = titulo;
            option.textContent = titulo;
            select.appendChild(option);
        });
    }

    function actualizarDashboard(libroSeleccionado) {
        let librosAMostrar = libroSeleccionado === "Todos" 
            ? Object.keys(datosGlobales) 
            : [libroSeleccionado];

        dibujarTarjetas(librosAMostrar);
        dibujarGrafico(librosAMostrar);
        generarPrediccion(librosAMostrar);
    }

    function dibujarTarjetas(libros) {
        const contenedor = document.getElementById('contenedorKPIs');
        contenedor.innerHTML = ''; // Limpiar tarjetas anteriores

        libros.forEach(titulo => {
            const datos = datosGlobales[titulo];
            // Obtener el último precio registrado
            const ultimaFecha = fechasGlobales[fechasGlobales.length - 1];
            const precioActual = datos.precios[ultimaFecha];

            if (!precioActual) return; // Si no hay precio hoy, lo saltamos

            // Lógica del Semáforo
            let claseEstado = '';
            let textoEstado = '';

            if (precioActual <= datos.min) {
                claseEstado = 'estado-verde';
                textoEstado = '🟢 Mínimo Histórico - ¡Comprar!';
            } else if (precioActual >= datos.max && datos.max !== datos.min) {
                claseEstado = 'estado-rojo';
                textoEstado = '🔴 Precio Máximo - Esperar';
            } else {
                claseEstado = 'estado-amarillo';
                textoEstado = '🟡 Precio Promedio - Observar';
            }

            const tarjeta = `
                <div class="kpi-card ${claseEstado}">
                    <h3>${titulo}</h3>
                    <div class="precio">${formatearDinero(precioActual)}</div>
                    <div class="minimo">Mejor precio visto: ${formatearDinero(datos.min)}</div>
                    <div class="estado">${textoEstado}</div>
                </div>
            `;
            contenedor.innerHTML += tarjeta;
        });
    }

    function generarPrediccion(libros) {
        const alertaBox = document.getElementById('alertaInteligente');
        const cantidadDias = fechasGlobales.length;

        if (cantidadDias < 7) {
            // Fase de aprendizaje: no hay suficientes datos para predecir
            alertaBox.className = 'alerta info';
            alertaBox.innerHTML = `🧠 <strong>Fase de Aprendizaje Activa:</strong> Llevas monitoreando ${cantidadDias} día(s). El motor de predicción necesita al menos 7 días de datos reales en la base de datos para detectar tendencias fiables.`;
            alertaBox.classList.remove('oculta');
        } else {
            // Aquí en el futuro (cuando pasen 7 días) puedes agregar lógica matemática real
            // Por ejemplo: comparar el promedio móvil de los últimos 3 días vs los últimos 7.
            alertaBox.className = 'alerta warning';
            alertaBox.innerHTML = `📊 <strong>Análisis activado:</strong> Hay suficientes datos históricos. (Aquí se inyectará la tendencia matemática de la semana).`;
            alertaBox.classList.remove('oculta');
        }
    }

    function dibujarGrafico(libros) {
        const ctx = document.getElementById('graficoPrecios').getContext('2d');
        
        // Destruir el gráfico anterior si existe para evitar superposiciones
        if (chartInstance) {
            chartInstance.destroy();
        }

        const datasets = libros.map(titulo => {
            const colorHue = Array.from(titulo).reduce((acc, char) => acc + char.charCodeAt(0), 0) % 360;
            const colorLindo = `hsl(${colorHue}, 70%, 50%)`;
            
            return {
                label: titulo,
                data: fechasGlobales.map(fecha => datosGlobales[titulo].precios[fecha] || null),
                borderColor: colorLindo,
                backgroundColor: colorLindo,
                tension: 0.3,
                spanGaps: true
            };
        });

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: fechasGlobales,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {
                                    label += formatearDinero(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }
});
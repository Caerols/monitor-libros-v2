document.addEventListener("DOMContentLoaded", () => {
    // 🔗 EL CAMBIO VITAL: Ahora apuntamos directamente al cerebro de la Bibliotecaria
    const API_URL = 'https://bibliotecaria-bot.onrender.com/api/historial';
    
    let chartInstance = null;
    let datosGlobales = {};
    let fechasGlobales = [];

    // Formateador de moneda chilena
    const formatearDinero = (monto) => {
        return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(monto);
    };

    // Iniciar conexión con la matriz
    fetch(API_URL)
        .then(response => {
            if (!response.ok) throw new Error("Fallo en la comunicación con el servidor");
            return response.json();
        })
        .then(data => {
            // 1. Apagar el mensaje de carga apenas lleguen los datos
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'none';
            
            // Asegurar que leemos bien el JSON (ya sea un array directo o un objeto)
            const historial = Array.isArray(data) ? data : data.historial;
            
            if (!historial || historial.length === 0) {
                const alertaBox = document.getElementById('alertaInteligente');
                if (alertaBox) {
                    alertaBox.style.display = 'block';
                    alertaBox.innerHTML = '⚠️ No hay datos registrados en el archivo todavía. Asegúrate de que el scraper haya finalizado su barrido.';
                }
                return;
            }

            // Extraer y ordenar fechas únicas
            fechasGlobales = [...new Set(historial.map(item => item.fecha))].sort();
            
            // Agrupar datos por libro
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
        .catch(error => {
            console.error("Error al cargar la API:", error);
            const loader = document.getElementById('loader');
            if (loader) {
                loader.style.color = '#dc3545';
                loader.innerHTML = '❌ Error de conexión. La Bibliotecaria podría estar reiniciando sus sistemas. Intenta actualizar la página en unos segundos.';
            }
        });

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
        generarPrediccion();
    }

    function dibujarTarjetas(libros) {
        // Conectamos con el ID exacto del HTML nuevo
        const contenedor = document.getElementById('kpi-container'); 
        if (!contenedor) return;
        
        contenedor.innerHTML = ''; // Limpiar tarjetas anteriores
        contenedor.style.display = 'flex';
        contenedor.style.flexWrap = 'wrap';
        contenedor.style.gap = '20px';

        libros.forEach(titulo => {
            const datos = datosGlobales[titulo];
            const ultimaFecha = fechasGlobales[fechasGlobales.length - 1];
            const precioActual = datos.precios[ultimaFecha];

            if (!precioActual) return; // Si justo ese libro no tiene precio hoy, lo salta

            // Lógica del Semáforo
            let claseEstado = '';
            let textoEstado = '';

            if (precioActual <= datos.min) {
                claseEstado = 'tendencia-baja'; // Clase CSS verde
                textoEstado = '🟢 Mínimo Histórico - ¡Comprar!';
            } else if (precioActual >= datos.max && datos.max !== datos.min) {
                claseEstado = 'tendencia-alta'; // Clase CSS roja
                textoEstado = '🔴 Precio Máximo - Esperar';
            } else {
                claseEstado = '';
                textoEstado = '🟡 Precio Promedio - Observar';
            }

            const tarjeta = `
                <div class="kpi-card">
                    <h3>${titulo}</h3>
                    <p class="${claseEstado}">${formatearDinero(precioActual)}</p>
                    <div style="font-size: 13px; color: #666; margin-top: 10px;">Mejor precio: ${formatearDinero(datos.min)}</div>
                    <div style="font-size: 13px; margin-top: 5px; font-weight: bold;">${textoEstado}</div>
                </div>
            `;
            contenedor.innerHTML += tarjeta;
        });
    }

    function generarPrediccion() {
        const alertaBox = document.getElementById('alertaInteligente');
        if (!alertaBox) return;
        
        const cantidadDias = fechasGlobales.length;

        // Le damos estilo vía JS para no depender del CSS
        alertaBox.style.padding = '15px';
        alertaBox.style.marginBottom = '20px';
        alertaBox.style.borderRadius = '8px';
        alertaBox.style.display = 'block';

        if (cantidadDias < 7) {
            alertaBox.style.backgroundColor = '#e7f3fe';
            alertaBox.style.color = '#31708f';
            alertaBox.style.border = '1px solid #bce8f1';
            alertaBox.innerHTML = `🧠 <strong>Fase de Aprendizaje Activa:</strong> Llevas monitoreando ${cantidadDias} día(s). El motor de predicción necesita al menos 7 días de datos reales para soltar info pro.`;
        } else {
            alertaBox.style.backgroundColor = '#fff3cd';
            alertaBox.style.color = '#856404';
            alertaBox.style.border = '1px solid #ffeeba';
            alertaBox.innerHTML = `📊 <strong>Análisis activado:</strong> Hay suficientes datos históricos para observar tendencias consistentes.`;
        }
    }

   function dibujarGrafico(libros) {
        const ctx = document.getElementById('graficoPrecios').getContext('2d');
        
        if (chartInstance) {
            chartInstance.destroy();
        }

        // 1. MOTOR DE VOLATILIDAD: Evaluar los libros recibidos
        let librosEvaluados = [];

        libros.forEach(titulo => {
            const datos = datosGlobales[titulo];
            
            // Si el max y min son iguales (o 0), significa que es un precio plano. Lo descartamos.
            const esPlano = datos.max === datos.min;
            
            // Calculamos cuánto varió en total (el "salto" de precio)
            const variacion = datos.max - datos.min;

            if (!esPlano) {
                librosEvaluados.push({
                    titulo: titulo,
                    variacion: variacion,
                    datosY: fechasGlobales.map(fecha => datos.precios[fecha] || null)
                });
            }
        });

        // 2. RANKING Y TOP 5: Si estamos viendo "Todos", mostramos solo el Top 5 más volátil.
        // Si el usuario eligió un libro específico en el filtro, saltamos este paso.
        let librosParaGraficar = librosEvaluados;
        
        if (libros.length > 1) { 
            // Ordenar de mayor a menor variación
            librosEvaluados.sort((a, b) => b.variacion - a.variacion);
            // Quedarse solo con los 5 primeros
            librosParaGraficar = librosEvaluados.slice(0, 5);
        }

        // Si todos los libros del filtro son "planos", detenemos el gráfico para no mostrar algo vacío
        if (librosParaGraficar.length === 0) {
            console.warn("Todos los precios son estáticos. No hay fluctuaciones para graficar.");
            // Opcional: Podrías inyectar un texto en el canvas o dejarlo vacío
            return; 
        }

        // 3. PREPARAR DATASETS PARA CHART.JS
        const datasets = librosParaGraficar.map(libroInfo => {
            const titulo = libroInfo.titulo;
            const colorHue = Array.from(titulo).reduce((acc, char) => acc + char.charCodeAt(0), 0) % 360;
            const colorLindo = `hsl(${colorHue}, 70%, 50%)`;
            
            return {
                label: titulo, // El nombre completo se guarda aquí
                data: libroInfo.datosY,
                borderColor: colorLindo,
                backgroundColor: colorLindo,
                tension: 0.3,
                spanGaps: true,
                borderWidth: 3,
                pointRadius: 4,
                pointHoverRadius: 7
            };
        });

        // 4. DIBUJAR EL GRÁFICO (Con la leyenda trucada)
        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: fechasGlobales,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: { 
                        position: window.innerWidth < 600 ? 'bottom' : 'top',
                        labels: {
                            boxWidth: window.innerWidth < 600 ? 10 : 40,
                            font: { size: window.innerWidth < 600 ? 10 : 12 },
                            usePointStyle: true,
                            padding: 20,
                            // MAGIA 1: Acortamos el texto de la leyenda a 35 caracteres
                            generateLabels: function(chart) {
                                const original = Chart.defaults.plugins.legend.labels.generateLabels;
                                const labels = original.call(this, chart);
                                labels.forEach(label => {
                                    if (label.text.length > 35) {
                                        label.text = label.text.substring(0, 35) + '...';
                                    }
                                });
                                return labels;
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(26, 35, 126, 0.9)', // Estilo Matriz
                        titleFont: { size: 14 },
                        callbacks: {
                            // MAGIA 2: Mostramos el título completo en el tooltip negro
                            title: function(context) {
                                return context[0].dataset.label; 
                            },
                            label: function(context) {
                                let label = ''; // Ocultamos el nombre aquí porque ya está en el título del tooltip
                                if (context.parsed.y !== null) {
                                    label += formatearDinero(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false, // Permite el zoom dramático en las curvas
                        ticks: {
                            callback: function(value) {
                                return formatearDinero(value);
                            }
                        }
                    }
                }
            }
        });
    }
});
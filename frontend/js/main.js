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
            
            // Asegurar que leemos bien el JSON
            const historial = Array.isArray(data) ? data : data.historial;
            
            if (!historial || historial.length === 0) {
                const alertaBox = document.getElementById('alertaInteligente');
                if (alertaBox) {
                    alertaBox.style.display = 'block';
                    alertaBox.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                    alertaBox.style.border = '1px solid var(--neon-rojo)';
                    alertaBox.style.color = 'var(--neon-rojo)';
                    alertaBox.innerHTML = '<i class="ph ph-warning-circle" style="margin-right:8px;"></i> No hay datos registrados en el archivo todavía. Asegúrate de que el scraper haya finalizado su barrido.';
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
                loader.style.color = 'var(--neon-rojo)';
                loader.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                loader.style.border = '1px solid var(--neon-rojo)';
                loader.innerHTML = '<i class="ph ph-x-circle" style="font-size: 38px; margin-bottom: 15px; display: inline-block;"></i><br>Error de conexión. La Bibliotecaria podría estar reiniciando sus sistemas.';
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

    // ACTIALIZACIÓN: Pasamos el libro y la lista a la función del Analista
    function actualizarDashboard(libroSeleccionado) {
        let librosAMostrar = libroSeleccionado === "Todos" 
            ? Object.keys(datosGlobales) 
            : [libroSeleccionado];

        dibujarTarjetas(librosAMostrar);
        dibujarGrafico(librosAMostrar);
        generarPrediccion(libroSeleccionado, librosAMostrar); 
    }

    function dibujarTarjetas(libros) {
        const contenedor = document.getElementById('kpi-container'); 
        if (!contenedor) return;
        
        contenedor.innerHTML = ''; 
        contenedor.style.display = 'flex';
        contenedor.style.flexWrap = 'wrap';
        contenedor.style.gap = '20px';

        libros.forEach(titulo => {
            const datos = datosGlobales[titulo];
            const ultimaFecha = fechasGlobales[fechasGlobales.length - 1];
            const precioActual = datos.precios[ultimaFecha];

            if (!precioActual) return;

            // Lógica del Semáforo
            let claseEstado = '';
            let textoEstado = '';

            if (precioActual <= datos.min) {
                claseEstado = 'tendencia-baja'; 
                textoEstado = '<i class="ph-fill ph-check-circle" style="margin-right: 5px;"></i> Mínimo Histórico - ¡Comprar!';
            } else if (precioActual >= datos.max && datos.max !== datos.min) {
                claseEstado = 'tendencia-alta'; 
                textoEstado = '<i class="ph-fill ph-warning" style="margin-right: 5px;"></i> Precio Máximo - Esperar';
            } else {
                claseEstado = '';
                textoEstado = '<i class="ph-fill ph-eye" style="color: var(--neon-ambar); margin-right: 5px;"></i> Precio Promedio - Observar';
            }

            const tarjeta = `
                <div class="kpi-card">
                    <h3>${titulo}</h3>
                    <p class="${claseEstado}">${formatearDinero(precioActual)}</p>
                    <div style="font-size: 13px; color: var(--texto-mutado); margin-top: 10px;">Mejor precio: ${formatearDinero(datos.min)}</div>
                    <div style="font-size: 13px; margin-top: 8px; font-weight: 600; color: var(--texto-base);">${textoEstado}</div>
                </div>
            `;
            contenedor.innerHTML += tarjeta;
        });
    }

    // EL NUEVO CEREBRO DEL ANALISTA INTELIGENTE
    function generarPrediccion(libroSeleccionado, libros) {
        const alertaBox = document.getElementById('alertaInteligente');
        if (!alertaBox) return;
        
        const cantidadDias = fechasGlobales.length;
        const ultimaFecha = fechasGlobales[fechasGlobales.length - 1];

        alertaBox.style.padding = '15px';
        alertaBox.style.marginBottom = '25px';
        alertaBox.style.borderRadius = '8px';
        alertaBox.style.display = 'block';

        // Validar si hay suficientes datos (mínimo 2 días para poder comparar)
        if (cantidadDias < 2) {
            alertaBox.style.backgroundColor = 'rgba(6, 182, 212, 0.1)';
            alertaBox.style.color = 'var(--neon-cyan)';
            alertaBox.style.border = '1px solid rgba(6, 182, 212, 0.3)';
            alertaBox.innerHTML = `<i class="ph ph-brain" style="font-size: 18px; vertical-align: middle; margin-right: 8px;"></i> <strong>Fase de Aprendizaje Activa:</strong> Recopilando datos. El motor necesita al menos 2 días de historial para emitir juicios de valor.`;
            return;
        }

        // Restablecemos colores por defecto (Ámbar)
        alertaBox.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
        alertaBox.style.color = 'var(--neon-ambar)';
        alertaBox.style.border = '1px solid rgba(245, 158, 11, 0.3)';

        // ==========================================
        // 1. REPORTE GLOBAL (Viendo todos los libros)
        // ==========================================
        if (libroSeleccionado === "Todos") {
            let cantidadMinimoHistorico = 0;
            let mejorDescuento = { titulo: '', porcentaje: 0, ahorro: 0 };

            libros.forEach(titulo => {
                const datos = datosGlobales[titulo];
                const precioActual = datos.precios[ultimaFecha];
                
                if (!precioActual) return;

                // Si está en el mínimo (y ha variado alguna vez)
                if (precioActual <= datos.min && datos.min !== datos.max) {
                    cantidadMinimoHistorico++;
                }

                // Buscar el descuento más agresivo respecto a su precio máximo
                const ahorroAbsoluto = datos.max - precioActual;
                const porcentaje = (datos.max > 0) ? (ahorroAbsoluto / datos.max) * 100 : 0;

                if (porcentaje > mejorDescuento.porcentaje) {
                    mejorDescuento = { titulo, porcentaje, ahorro: ahorroAbsoluto };
                }
            });

            let mensajeHTML = `<i class="ph ph-radar" style="font-size: 18px; vertical-align: middle; margin-right: 8px;"></i> <strong>Reporte de Mercado Global:</strong> `;
            
            if (cantidadMinimoHistorico > 0) {
                mensajeHTML += `Hay <span style="color: var(--neon-verde); font-weight: bold;">${cantidadMinimoHistorico} expediente(s)</span> en su mínimo histórico listo(s) para compra. `;
            } else {
                mensajeHTML += `Ningún libro ha tocado fondo histórico hoy. Mantén vigilancia. `;
            }

            if (mejorDescuento.porcentaje > 0) {
                mensajeHTML += `<br><span style="margin-left: 28px; font-size: 13px; color: var(--texto-brillante); display: inline-block; margin-top: 5px;">🔥 <strong>Mayor Oportunidad:</strong> <em>'${mejorDescuento.titulo}'</em> tiene un <strong>${Math.round(mejorDescuento.porcentaje)}% de descuento</strong> (Ahorras ${formatearDinero(mejorDescuento.ahorro)} respecto a su peak más caro).</span>`;
            }

            alertaBox.innerHTML = mensajeHTML;
        } 
        // ==========================================
        // 2. REPORTE INDIVIDUAL (Viendo 1 solo libro)
        // ==========================================
        else {
            const titulo = libroSeleccionado;
            const datos = datosGlobales[titulo];
            const precioActual = datos.precios[ultimaFecha];
            
            if (!precioActual) return;

            const sobreprecio = precioActual - datos.min;
            const ahorroDesdeMax = datos.max - precioActual;

            let analisisHTML = `<i class="ph ph-crosshair" style="font-size: 18px; vertical-align: middle; margin-right: 8px;"></i> <strong>Inteligencia de Expediente:</strong> `;

            if (precioActual <= datos.min && datos.max !== datos.min) {
                // Color verde agresivo para compras claras
                alertaBox.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
                alertaBox.style.color = 'var(--neon-verde)';
                alertaBox.style.border = '1px solid rgba(16, 185, 129, 0.3)';
                analisisHTML += `¡Condición ideal detectada! El precio está en el piso histórico. No encontrarás una oportunidad matemática mejor. <strong style="text-transform: uppercase;">Veredicto: Comprar de inmediato.</strong>`;
            } else if (precioActual >= datos.max && datos.max !== datos.min) {
                // Color rojo alerta para evitar compras malas
                alertaBox.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                alertaBox.style.color = 'var(--neon-rojo)';
                alertaBox.style.border = '1px solid rgba(239, 68, 68, 0.3)';
                analisisHTML += `Mercado saturado. Estás pagando el precio más alto registrado. Si compras hoy, perderías ${formatearDinero(sobreprecio)} respecto a su mejor momento. <strong style="text-transform: uppercase;">Veredicto: Evitar compra y esperar caída.</strong>`;
            } else if (datos.max === datos.min) {
                // Precio estático
                analisisHTML += `El precio de este libro ha estado estático sin variaciones desde que se inició el rastreo. <strong style="text-transform: uppercase;">Veredicto: Sin volatilidad, puedes comprar cuando quieras.</strong>`;
            } else {
                // Precio intermedio
                analisisHTML += `Precio estabilizado a la mitad de su ciclo. Estás pagando un sobreprecio de ${formatearDinero(sobreprecio)} comparado al mínimo, pero ya bajó ${formatearDinero(ahorroDesdeMax)} desde su pico más caro. <strong style="text-transform: uppercase;">Veredicto: Mantener en observación.</strong>`;
            }

            alertaBox.innerHTML = analisisHTML;
        }
    }

   function dibujarGrafico(libros) {
        const ctx = document.getElementById('graficoPrecios').getContext('2d');
        
        if (chartInstance) {
            chartInstance.destroy();
        }

        Chart.defaults.font.family = "'Inter', Tahoma, Geneva, Verdana, sans-serif";
        Chart.defaults.color = '#cbd5e1'; 

        let librosEvaluados = [];

        libros.forEach(titulo => {
            const datos = datosGlobales[titulo];
            const esPlano = datos.max === datos.min;
            const variacion = datos.max - datos.min;

            if (!esPlano) {
                librosEvaluados.push({
                    titulo: titulo,
                    variacion: variacion,
                    datosY: fechasGlobales.map(fecha => datos.precios[fecha] || null)
                });
            }
        });

        let librosParaGraficar = librosEvaluados;
        
        if (libros.length > 1) { 
            librosEvaluados.sort((a, b) => b.variacion - a.variacion);
            librosParaGraficar = librosEvaluados.slice(0, 5);
        }

        if (librosParaGraficar.length === 0) {
            return; 
        }

        const datasets = librosParaGraficar.map(libroInfo => {
            const titulo = libroInfo.titulo;
            const colorHue = Array.from(titulo).reduce((acc, char) => acc + char.charCodeAt(0), 0) % 360;
            const colorLindo = `hsl(${colorHue}, 80%, 65%)`;
            
            return {
                label: titulo, 
                data: libroInfo.datosY,
                borderColor: colorLindo,
                backgroundColor: colorLindo,
                tension: 0.3,
                spanGaps: true,
                borderWidth: 3,
                pointRadius: 4,
                pointHoverRadius: 7,
                pointBackgroundColor: 'var(--bg-tarjeta)',
                pointBorderWidth: 2
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
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: { 
                        position: window.innerWidth < 600 ? 'bottom' : 'top',
                        labels: {
                            color: '#cbd5e1',
                            boxWidth: window.innerWidth < 600 ? 10 : 40,
                            font: { size: window.innerWidth < 600 ? 10 : 12 },
                            usePointStyle: true,
                            padding: 20,
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
                        backgroundColor: 'rgba(15, 23, 42, 0.95)', 
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        titleColor: '#f8fafc',
                        bodyColor: '#cbd5e1',
                        titleFont: { size: 14, family: "'Inter', sans-serif" },
                        padding: 12,
                        callbacks: {
                            title: function(context) {
                                return context[0].dataset.label; 
                            },
                            label: function(context) {
                                let label = ''; 
                                if (context.parsed.y !== null) {
                                    label += formatearDinero(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        border: { display: false }
                    },
                    y: {
                        beginAtZero: false, 
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        border: { display: false },
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
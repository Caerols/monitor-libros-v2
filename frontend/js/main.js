document.addEventListener("DOMContentLoaded", () => {
    const API_URL = 'https://api-libros-7k6t.onrender.com/api/historial';
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
            // 1. Apagar el mensaje de carga apenas lleguen los datos
            const loader = document.getElementById('loader');
            if (loader) loader.style.display = 'none';
            
            // Asegurar que leemos bien el JSON (ya sea un array directo o un objeto)
            const historial = Array.isArray(data) ? data : data.historial;
            
            fechasGlobales = [...new Set(historial.map(item => item.fecha))];
            
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
            if (loader) loader.innerHTML = '❌ Error al conectar con el servidor de Render.';
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
        generarPrediccion(librosAMostrar);
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

    function generarPrediccion(libros) {
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
            alertaBox.innerHTML = `📊 <strong>Análisis activado:</strong> Hay suficientes datos históricos.`;
        }
    }

    function dibujarGrafico(libros) {
        const ctx = document.getElementById('graficoPrecios').getContext('2d');
        
        if (chartInstance) {
            chartInstance.destroy();
        }

        const datasets = libros.map(titulo => {
            // Genera un color único por libro basado en su nombre
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
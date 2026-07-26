document.addEventListener('DOMContentLoaded', () => {
    
    // =========================================================
    // 1. MOTOR MATEMÁTICO (Extremos y Totales)
    // =========================================================
    function calcularEstadisticas(libros) {
        if (!libros || libros.length === 0) return;

        const totalLibros = libros.length;
        let totalPaginas = 0;
        let totalPalabras = 0;
        
        let paginasLeidas = 0;
        let palabrasLeidas = 0;
        
        let libroMasLargo = null;
        let libroMasCorto = null;

        libros.forEach(libro => {
            const paginas = parseInt(libro.num_paginas) || 0;
            const palabras = parseInt(libro.palabras) || (paginas * 250); 

            // Suma global
            totalPaginas += paginas;
            totalPalabras += palabras;

            // Suma de lectura real (Solo si está finalizado)
            if (libro.estado_lectura === "Finalizado") {
                paginasLeidas += paginas;
                palabrasLeidas += palabras;
            }

            // Encontrar extremos
            if (paginas > 0) {
                if (!libroMasLargo || paginas > libroMasLargo.num_paginas) {
                    libroMasLargo = libro;
                }
                if (!libroMasCorto || paginas < libroMasCorto.num_paginas) {
                    libroMasCorto = libro;
                }
            }
        });

        const promedioPaginas = totalLibros > 0 ? Math.round(totalPaginas / totalLibros) : 0;

        // Inyectar Totales
        document.getElementById('stat-total-libros').innerText = totalLibros.toLocaleString('es-CL');
        document.getElementById('stat-total-paginas').innerText = totalPaginas.toLocaleString('es-CL');
        document.getElementById('stat-total-palabras').innerText = totalPalabras.toLocaleString('es-CL');
        document.getElementById('stat-promedio-paginas').innerHTML = `${promedioPaginas.toLocaleString('es-CL')} <span class="minimo" style="font-size: 14px;">págs</span>`;

        // Inyectar Progreso Leído
        document.getElementById('stat-paginas-leidas').innerText = paginasLeidas.toLocaleString('es-CL');
        document.getElementById('stat-palabras-leidas').innerText = palabrasLeidas.toLocaleString('es-CL');

        // Inyectar Extremos
        if (libroMasLargo) {
            document.getElementById('stat-mas-largo').innerText = libroMasLargo.titulo;
            document.getElementById('stat-largo-paginas').innerText = `${libroMasLargo.num_paginas} páginas`;
        }
        if (libroMasCorto) {
            document.getElementById('stat-mas-corto').innerText = libroMasCorto.titulo;
            document.getElementById('stat-corto-paginas').innerText = `${libroMasCorto.num_paginas} páginas`;
        }
    }

// =========================================================
    // 2. MOTOR DEL ADN LITERARIO (Metadatos)
    // =========================================================
    function calcularADN(libros) {
        if (!libros || libros.length === 0) return;

        let contadorAutores = {};
        let contadorGeneros = {};
        let contadorEditoriales = {};
        
        let libroMasAntiguo = null;
        let libroMasNuevo = null;

        libros.forEach(libro => {
            // 2.1 Procesar Favoritos
            if (libro.autor && libro.autor.trim() !== "") {
                contadorAutores[libro.autor] = (contadorAutores[libro.autor] || 0) + 1;
            }
            if (libro.genero && libro.genero.trim() !== "") {
                contadorGeneros[libro.genero] = (contadorGeneros[libro.genero] || 0) + 1;
            }
            if (libro.editorial && libro.editorial.trim() !== "") {
                contadorEditoriales[libro.editorial] = (contadorEditoriales[libro.editorial] || 0) + 1;
            }

            // 2.2 MÁQUINA DEL TIEMPO (Ahora acepta años a.C. con números negativos)
            const anioNum = parseInt(libro.anio_publicacion);

            // Aceptamos cualquier número válido que NO sea 0 (0 suele ser el valor por defecto de "vacío")
            if (!isNaN(anioNum) && anioNum !== 0) {
                libro._anioCalculado = anioNum; 

                // Matemáticamente -500 es menor que 1990, así que la lógica funciona perfecto
                if (!libroMasAntiguo || anioNum < libroMasAntiguo._anioCalculado) {
                    libroMasAntiguo = libro;
                }
                if (!libroMasNuevo || anioNum > libroMasNuevo._anioCalculado) {
                    libroMasNuevo = libro;
                }
            }
        });

        // Función interna para sacar al ganador
        function encontrarFavorito(contador) {
            let favorito = "-";
            let maxVotos = 0;
            for (const [nombre, votos] of Object.entries(contador)) {
                if (votos > maxVotos) {
                    maxVotos = votos;
                    favorito = nombre;
                }
            }
            return favorito;
        }

        // Función mágica para formatear años negativos
        function formatearAnio(anio) {
            if (anio < 0) return `${Math.abs(anio)} a.C.`; // Math.abs quita el signo menos
            return anio;
        }

        // 3. Inyectar Resultados en el HTML
        document.getElementById('adn-autor').innerText = encontrarFavorito(contadorAutores);
        document.getElementById('adn-genero').innerText = encontrarFavorito(contadorGeneros);
        document.getElementById('adn-editorial').innerText = encontrarFavorito(contadorEditoriales);

        if (libroMasAntiguo) {
            document.getElementById('adn-reliquia').innerText = libroMasAntiguo.titulo;
            document.getElementById('adn-reliquia-ano').innerText = `Año: ${formatearAnio(libroMasAntiguo._anioCalculado)}`;
        }
        
        if (libroMasNuevo) {
            document.getElementById('adn-nuevo').innerText = libroMasNuevo.titulo;
            document.getElementById('adn-nuevo-ano').innerText = `Año: ${formatearAnio(libroMasNuevo._anioCalculado)}`;
        }
    }

    // =========================================================
    // 3. MOTOR DE GRÁFICOS (Chart.js) - MATRIZ PROFUNDA
    // =========================================================
    function renderizarGraficos(libros) {
        if (!libros || libros.length === 0) return;

        let conteoEstados = { "Finalizado": 0, "En lectura": 0, "Pendiente": 0, "No iniciado": 0 };
        let conteoCalificaciones = { "5": 0, "4": 0, "3": 0, "2": 0, "1": 0, "0": 0 };

        libros.forEach(libro => {
            const estado = libro.estado_lectura || "No iniciado";
            if (conteoEstados[estado] !== undefined) conteoEstados[estado]++;

            const calificacion = libro.calificacion || 0;
            if (conteoCalificaciones[calificacion] !== undefined) conteoCalificaciones[calificacion]++;
        });

        // 1. Tipografía y color base adaptados a la oscuridad
        Chart.defaults.font.family = "'Inter', Tahoma, Geneva, Verdana, sans-serif";
        Chart.defaults.color = '#cbd5e1'; // Gris perla brillante para textos

        // --- DIBUJAR: Gráfico de Estados (Doughnut) ---
        const ctxEstados = document.getElementById('graficoEstados').getContext('2d');
        new Chart(ctxEstados, {
            type: 'doughnut',
            data: {
                labels: ['Finalizado', 'En lectura', 'Pendiente', 'No iniciado'],
                datasets: [{
                    data: [
                        conteoEstados["Finalizado"], 
                        conteoEstados["En lectura"], 
                        conteoEstados["Pendiente"], 
                        conteoEstados["No iniciado"]
                    ],
                    // Paleta de tonos Neón (Verde, Ámbar, Rojo, Gris Carbón)
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444', '#334155'],
                    borderWidth: 3,
                    borderColor: '#1e293b' // Se camufla exacto con el fondo de la tarjeta
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { 
                        position: 'bottom',
                        labels: { boxWidth: 12, padding: 10, color: '#cbd5e1' }
                    }
                }
            }
        });

        // --- DIBUJAR: Gráfico de Calificaciones (Bar) ---
        const ctxCalificaciones = document.getElementById('graficoCalificaciones').getContext('2d');
        new Chart(ctxCalificaciones, {
            type: 'bar',
            data: {
                labels: ['5 ⭐', '4 ⭐', '3 ⭐', '2 ⭐', '1 ⭐', 'Sin nota'],
                datasets: [{
                    label: 'Cantidad de Libros',
                    data: [
                        conteoCalificaciones["5"], 
                        conteoCalificaciones["4"], 
                        conteoCalificaciones["3"], 
                        conteoCalificaciones["2"], 
                        conteoCalificaciones["1"],
                        conteoCalificaciones["0"]
                    ],
                    backgroundColor: '#06b6d4', // Cian eléctrico para resaltar brutal
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { autoSkip: false, maxRotation: 0, minRotation: 0, color: '#cbd5e1' },
                        grid: { 
                            color: 'rgba(255, 255, 255, 0.05)', // Cuadrícula casi invisible
                        },
                        border: { display: false } // Quita la línea gruesa del eje
                    },
                    y: { 
                        beginAtZero: true, 
                        ticks: { stepSize: 1, color: '#cbd5e1' },
                        grid: { 
                            color: 'rgba(255, 255, 255, 0.05)' 
                        },
                        border: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // =========================================================
    // 4. CONEXIÓN A LA BASE DE DATOS
    // =========================================================
    const API_URL = 'https://bibliotecaria-bot.onrender.com/api/biblioteca/catalogo';

    fetch(API_URL)
        .then(response => {
            if (!response.ok) throw new Error("Fallo en la comunicación con la matriz central");
            return response.json();
        })
        .then(data => {
            const catalogo = data.catalogo;
            if (catalogo && catalogo.length > 0) {
                calcularEstadisticas(catalogo);
                calcularADN(catalogo); // Activamos el nuevo cerebro de metadatos
                renderizarGraficos(catalogo); 
            }
        })
        .catch(error => {
            console.error("Error al cargar el catálogo para estadísticas:", error);
            document.getElementById('stat-total-libros').innerText = "Error";
            document.getElementById('stat-total-libros').style.color = "#d32f2f";
        });
});
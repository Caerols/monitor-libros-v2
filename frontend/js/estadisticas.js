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
    // 2. MOTOR DE GRÁFICOS (Chart.js)
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

        Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
        Chart.defaults.color = '#666';

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
                    backgroundColor: ['#4caf50', '#ff9800', '#f44336', '#9e9e9e'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false, // ¡Clave para que respete el tamaño del div!
                plugins: {
                    legend: { 
                        position: 'bottom',
                        labels: { boxWidth: 12, padding: 10 }
                    }
                }
            }
        });

        // --- DIBUJAR: Gráfico de Calificaciones (Bar) ---
        const ctxCalificaciones = document.getElementById('graficoCalificaciones').getContext('2d');
        new Chart(ctxCalificaciones, {
            type: 'bar',
            data: {
                labels: ['⭐⭐⭐⭐⭐', '⭐⭐⭐⭐', '⭐⭐⭐', '⭐⭐', '⭐', 'Sin nota'],
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
                    backgroundColor: '#1abc9c',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false, // ¡Clave aquí también!
                scales: {
                    y: { 
                        beginAtZero: true, 
                        ticks: { stepSize: 1 } 
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // =========================================================
    // 3. CONEXIÓN A LA BASE DE DATOS
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
                renderizarGraficos(catalogo); // Activamos los gráficos
            }
        })
        .catch(error => {
            console.error("Error al cargar el catálogo para estadísticas:", error);
            document.getElementById('stat-total-libros').innerText = "Error";
            document.getElementById('stat-total-libros').style.color = "#d32f2f";
        });
});
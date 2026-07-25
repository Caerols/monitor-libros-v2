document.addEventListener('DOMContentLoaded', () => {
    
    // =========================================================
    // 1. MOTOR MATEMÁTICO
    // =========================================================
    function calcularEstadisticas(libros) {
        if (!libros || libros.length === 0) return;

        const totalLibros = libros.length;
        let totalPaginas = 0;
        let totalPalabras = 0;
        
        let libroMasLargo = null;
        let libroMasCorto = null;

        libros.forEach(libro => {
            // Parseo seguro de números
            const paginas = parseInt(libro.num_paginas) || 0;
            // Si no hay palabras, estimamos 250 por página
            const palabras = parseInt(libro.palabras) || (paginas * 250); 

            totalPaginas += paginas;
            totalPalabras += palabras;

            // Encontrar los extremos (ignorando libros con 0 páginas para no falsear datos)
            if (paginas > 0) {
                if (!libroMasLargo || paginas > libroMasLargo.num_paginas) {
                    libroMasLargo = libro;
                }
                if (!libroMasCorto || paginas < libroMasCorto.num_paginas) {
                    libroMasCorto = libro;
                }
            }
        });

        // Cálculos derivados
        const promedioPaginas = totalLibros > 0 ? Math.round(totalPaginas / totalLibros) : 0;

        // Inyección en el DOM (Usando formato chileno para los miles)
        document.getElementById('stat-total-libros').innerText = totalLibros.toLocaleString('es-CL');
        document.getElementById('stat-total-paginas').innerText = totalPaginas.toLocaleString('es-CL');
        document.getElementById('stat-total-palabras').innerText = totalPalabras.toLocaleString('es-CL');
        
        document.getElementById('stat-promedio-paginas').innerHTML = `${promedioPaginas.toLocaleString('es-CL')} <span class="minimo" style="font-size: 14px;">págs</span>`;

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
    // 2. CONEXIÓN A LA BASE DE DATOS
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
                // Le pasamos los libros reales al motor matemático
                calcularEstadisticas(catalogo);
            }
        })
        .catch(error => {
            console.error("Error al cargar el catálogo para estadísticas:", error);
            // Si hay un error, mostramos un mensaje visual en una de las tarjetas principales
            document.getElementById('stat-total-libros').innerText = "Error";
            document.getElementById('stat-total-libros').style.color = "#d32f2f";
        });
});
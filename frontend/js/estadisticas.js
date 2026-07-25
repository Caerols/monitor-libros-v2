document.addEventListener('DOMContentLoaded', async () => {
    // Aquí llamamos a la misma fuente de datos que usa tu biblioteca.html
    // Reemplaza esta URL si tu API endpoint es diferente.
    try {
        // Simulamos la carga de datos (Debes conectar tu fetch real aquí si usas una API)
        // const response = await fetch('/api/libros'); 
        // const catalogo = await response.json();
        
        // Si estás usando window.catalogoGlobal o localStorage por ahora,
        // asegúrate de pasarle el arreglo de libros a esta función.
        
        // Función principal del motor analítico
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

                // Encontrar los extremos (ignorando libros con 0 páginas)
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
        // 🚀 INICIALIZACIÓN 
        // =========================================================
        // IMPORTANTE: Aquí debes pasar tu arreglo real de libros. 
        // Si tu variable global es 'catalogo', usa: calcularEstadisticas(catalogo);
        
        // EJEMPLO MOCK (Para que veas cómo funciona antes de conectar tu API):
        /*
        const mockCatalogo = [
            { titulo: "El Ladrillo", num_paginas: 1200, palabras: 300000 },
            { titulo: "El Folletito", num_paginas: 50, palabras: 12500 }
        ];
        calcularEstadisticas(mockCatalogo);
        */

    } catch (error) {
        console.error("Error al arrancar el motor de estadísticas:", error);
    }
});
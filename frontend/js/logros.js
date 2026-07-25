document.addEventListener('DOMContentLoaded', () => {

    const API_URL = 'https://bibliotecaria-bot.onrender.com/api/biblioteca/catalogo';

    fetch(API_URL)
        .then(response => response.json())
        .then(data => {
            const catalogo = data.catalogo;
            if (catalogo && catalogo.length > 0) {
                calcularLogros(catalogo);
            }
        })
        .catch(error => {
            console.error("Error al cargar el catálogo para logros:", error);
        });

    function calcularLogros(libros) {
        // 1. Contadores y Métricas
        let librosFinalizados = 0;
        let paginasLeidas = 0;
        let palabrasLeidas = 0;
        let librosPendientes = 0;
        let obrasMaestras = 0; // 5 estrellas
        let decepciones = 0;   // 1 o 2 estrellas
        let maratonLogrado = false;

        libros.forEach(libro => {
            const paginas = parseInt(libro.num_paginas) || 0;
            const palabras = parseInt(libro.palabras) || (paginas * 250);
            const calificacion = parseInt(libro.calificacion) || 0;
            const estado = libro.estado_lectura;

            // Lógica solo para libros "Finalizados"
            if (estado === "Finalizado") {
                librosFinalizados++;
                paginasLeidas += paginas;
                palabrasLeidas += palabras;

                if (paginas > 800) {
                    maratonLogrado = true;
                }
            }

            // Lógica por Estados
            if (estado === "Pendiente") {
                librosPendientes++;
            }

            // Lógica por Calificaciones (Solo libros finalizados deberían contar, pero evaluamos todos)
            if (calificacion === 5) obrasMaestras++;
            if (calificacion === 1 || calificacion === 2) decepciones++;
        });

        // 2. Función auxiliar para actualizar tarjetas
        function actualizarLogro(idTarjeta, idTexto, actual, meta, textoCompletado = "¡Completado!") {
            const tarjeta = document.getElementById(idTarjeta);
            const texto = document.getElementById(idTexto);

            if (!tarjeta || !texto) return;

            // Formatear números con puntos (ej: 10.000)
            const actualStr = actual.toLocaleString('es-CL');
            const metaStr = meta.toLocaleString('es-CL');

            if (actual >= meta) {
                tarjeta.classList.remove('bloqueado');
                texto.innerText = textoCompletado;
            } else {
                texto.innerText = `${actualStr} / ${metaStr}`;
            }
        }

        // 3. Evaluar cada logro
        actualizarLogro('logro-iniciado', 'progreso-iniciado', librosFinalizados, 1);
        actualizarLogro('logro-devorador', 'progreso-devorador', paginasLeidas, 10000);
        actualizarLogro('logro-erudito', 'progreso-erudito', palabrasLeidas, 1000000);
        actualizarLogro('logro-diogenes', 'progreso-diogenes', librosPendientes, 15);
        actualizarLogro('logro-oro', 'progreso-oro', obrasMaestras, 5);
        actualizarLogro('logro-critico', 'progreso-critico', decepciones, 3);

        // El caso especial de la Maratón (Booleano, no numérico gradual)
        const tarjetaMaraton = document.getElementById('logro-maraton');
        const textoMaraton = document.getElementById('progreso-maraton');
        if (maratonLogrado) {
            tarjetaMaraton.classList.remove('bloqueado');
            textoMaraton.innerText = "¡Completado!";
        }
    }
});
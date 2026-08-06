document.addEventListener("DOMContentLoaded", () => {
    // =====================================================================
    // MOTOR DE CARGA INTERACTIVA - MATRIZ PROFUNDA
    // =====================================================================

    // Array de mensajes de actividad de la "Bibliotecaria"
    const loadingMessages = [
        'Interceptando señales de mercado...',
        'Filtrando datos de proveedores locales...',
        'Verificando inventarios globales...',
        'Comparando fluctuaciones de precios...',
        'Analizando tendencias de mercado...',
        'Calculando puntos de decisión...'
    ];

    let messageIndex = 0;
    const messageElement = document.getElementById('loading-message-text');

    function cycleLoadingMessages() {
        if (messageElement) {
            // Actualiza el texto con el siguiente mensaje de la lista
            messageElement.innerText = loadingMessages[messageIndex];
            // Incrementa el índice y usa el operador % (módulo) para volver a empezar
            messageIndex = (messageIndex + 1) % loadingMessages.length;
        }
    }

    // Comienza a ciclar los mensajes de inmediato
    cycleLoadingMessages();

    // Configura un temporizador para ciclar los mensajes cada 2.5 segundos
    // (Asegúrate de que 'messageElement' exista antes de configurar el intervalo)
    if (messageElement) {
        setInterval(cycleLoadingMessages, 2500); 
    }

    // =====================================================================
    // Aquí es donde en el futuro, cuando tengas la lógica de datos,
    // harías el fetch y, al recibir los resultados, ocultarías esta tarjeta
    // de carga y mostrarías los gráficos de "Fluctuación Histórica".
    // =====================================================================
});
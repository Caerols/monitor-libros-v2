document.addEventListener("DOMContentLoaded", () => {
    // =====================================================================
    // 1. MOTOR DE RENDERIZADO DEL CATÁLOGO (FLIP CARDS)
    // =====================================================================
    const API_URL = 'https://bibliotecaria-bot.onrender.com/api/biblioteca/catalogo';
    const contenedorCatalogo = document.getElementById('catalogo-container');

    // Formateador de dinero chileno
    const formatearDinero = (monto) => {
        if (!monto) return "No registrado";
        return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(monto);
    };

    // Función para asignar colores a las medallas (badges) según el estado
    const obtenerClaseEstado = (estado) => {
        switch(estado) {
            case 'En lectura': return 'en-lectura';
            case 'Finalizado': return 'leido';
            case 'No iniciado': 
            case 'Pendiente': return 'pendiente';
            default: return 'pendiente';
        }
    };

    // Función para dibujar las estrellas
    const generarEstrellas = (calificacion) => {
        if (!calificacion) return "Sin calificar";
        return "⭐".repeat(calificacion);
    };

    // Extraer datos de la API y dibujar tarjetas
    fetch(API_URL)
        .then(response => {
            if (!response.ok) throw new Error("Fallo en la comunicación con la matriz central");
            return response.json();
        })
        .then(data => {
            const catalogo = data.catalogo;
            
            if (!catalogo || catalogo.length === 0) {
                contenedorCatalogo.innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 40px; background: white; border-radius: 12px;">
                        <h3>🗂️ Tu biblioteca está vacía</h3>
                        <p>Aún no has registrado ningún libro en tu colección personal.</p>
                    </div>`;
                return;
            }

            // Limpiar la tarjeta de prueba (mock)
            contenedorCatalogo.innerHTML = '';

            // Generar tarjetas dinámicamente
            catalogo.forEach(libro => {
                const claseEstado = obtenerClaseEstado(libro.estado_lectura);
                const precioTexto = formatearDinero(libro.precio_pagado);
                const estrellas = generarEstrellas(libro.calificacion);
                const observaciones = libro.observaciones ? `<em>"${libro.observaciones}"</em>` : "<em>Sin observaciones.</em>";

                const tarjetaHTML = `
                    <div class="book-card">
                        <div class="book-card-inner">
                            
                            <!-- FRENTE -->
                            <div class="book-card-front">
                                <div class="portada-placeholder">
                                    <span>${libro.titulo}</span>
                                </div>
                                <div class="book-info-front">
                                    <h3>${libro.titulo}</h3>
                                    <p class="autor">${libro.autor}</p>
                                    <div class="book-badges">
                                        <span class="badge badge-estado ${claseEstado}">${libro.estado_lectura}</span>
                                        <span class="badge badge-rating">${estrellas}</span>
                                    </div>
                                </div>
                            </div>

                            <!-- REVERSO -->
                            <div class="book-card-back">
                                <h3>Detalles Técnicos</h3>
                                <ul class="book-details-list">
                                    <li><strong>Género:</strong> ${libro.genero}</li>
                                    <li><strong>Editorial:</strong> ${libro.editorial || 'No especificada'}</li>
                                    <li><strong>Páginas:</strong> ${libro.num_paginas || 0}</li>
                                    <li><strong>ISBN:</strong> ${libro.isbn || 'N/A'}</li>
                                    <li><strong>Formato:</strong> ${libro.formato || 'Físico'}</li>
                                </ul>
                                
                                <div class="book-finanzas">
                                    💰 <strong>Tienda:</strong> ${libro.tienda || 'Desconocida'}<br>
                                    💸 <strong>Precio:</strong> ${precioTexto}<br>
                                    📅 <strong>Fecha:</strong> ${libro.fecha_compra || 'No registrada'}
                                </div>

                                <div class="book-observaciones">
                                    ${observaciones}
                                </div>
                            </div>

                        </div>
                    </div>
                `;
                contenedorCatalogo.innerHTML += tarjetaHTML;
            });
        })
        .catch(error => {
            console.error("Error al cargar el catálogo:", error);
            if (contenedorCatalogo) {
                contenedorCatalogo.innerHTML = `
                    <div style="grid-column: 1 / -1; color: #d32f2f; text-align: center; padding: 20px;">
                        ❌ Error de conexión con la base de datos de la Bibliotecaria.
                    </div>`;
            }
        });

    // =====================================================================
    // 2. LÓGICA DEL MODAL Y AUTOCOMPLETADO MÁGICO (GOOGLE BOOKS API)
    // =====================================================================
    const modal = document.getElementById('modal-libro');
    const btnAbrir = document.getElementById('btn-abrir-modal');
    const btnCerrar = document.getElementById('btn-cerrar-modal');
    const btnAutocompletar = document.getElementById('btn-autocompletar');
    const mensajeInvestigacion = document.getElementById('mensaje-investigacion');

    // Manejo de apertura y cierre del Modal
    if (btnAbrir && modal && btnCerrar) {
        btnAbrir.onclick = () => modal.style.display = "block";
        btnCerrar.onclick = () => modal.style.display = "none";
        
        // Cerrar modal si el usuario hace clic fuera de la caja blanca
        window.onclick = (event) => { 
            if (event.target === modal) {
                modal.style.display = "none"; 
            }
        };
    }

// Evento de la Bibliotecaria investigando directamente desde el navegador (Bypass Render)
    if (btnAutocompletar) {
        btnAutocompletar.addEventListener('click', async () => {
            const titulo = document.getElementById('form-titulo').value.trim();
            const autor = document.getElementById('form-autor').value.trim();

            if (!titulo || !autor) {
                mensajeInvestigacion.style.color = "#d32f2f"; 
                mensajeInvestigacion.innerText = "⚠️ Necesito el título y el autor para iniciar la búsqueda.";
                return;
            }

            mensajeInvestigacion.style.color = "#1565c0"; 
            mensajeInvestigacion.innerText = "🔍 Interceptando señal de Google Books... espera.";
            btnAutocompletar.disabled = true;
            btnAutocompletar.style.opacity = "0.7";

            try {
                // BYPASS: Atacamos la API de Google directamente desde el navegador del usuario
                const queryEncoded = encodeURIComponent(`${titulo} ${autor}`);
                const urlGoogle = `https://www.googleapis.com/books/v1/volumes?q=${queryEncoded}&maxResults=1&langRestrict=es`;
                
                const response = await fetch(urlGoogle);
                if (!response.ok) throw new Error("Google rechazó la conexión local.");
                
                const data = await response.json();

                if (data.items && data.items.length > 0) {
                    const info = data.items[0].volumeInfo;
                    
                    // Extraer páginas
                    const paginas = info.pageCount || "";
                    
                    // Extraer ISBN limpio
                    let isbnLimpio = "";
                    if (info.industryIdentifiers) {
                        const isbn13 = info.industryIdentifiers.find(id => id.type === 'ISBN_13');
                        isbnLimpio = isbn13 ? isbn13.identifier : info.industryIdentifiers[0].identifier;
                    }

                    // Rellenar el formulario
                    document.getElementById('form-editorial').value = info.publisher || "";
                    document.getElementById('form-anio').value = info.publishedDate ? info.publishedDate.substring(0, 4) : "";
                    document.getElementById('form-paginas').value = paginas;
                    document.getElementById('form-palabras').value = paginas ? paginas * 250 : "";
                    document.getElementById('form-isbn').value = isbnLimpio;
                    document.getElementById('form-resumen').value = info.description || "Sin resumen disponible.";
                    
                    mensajeInvestigacion.style.color = "#2e7d32"; 
                    mensajeInvestigacion.innerText = "✅ Expediente extraído vía Bypass con éxito.";
                } else {
                    mensajeInvestigacion.style.color = "#d32f2f";
                    mensajeInvestigacion.innerText = "❌ Los archivos de Google no tienen este libro.";
                }
            } catch (error) {
                console.error("Error en Bypass:", error);
                mensajeInvestigacion.style.color = "#d32f2f";
                mensajeInvestigacion.innerText = "⚠️ Error al conectar con Google Books.";
            } finally {
                btnAutocompletar.disabled = false;
                btnAutocompletar.style.opacity = "1";
            }
        });
    }
});
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
                                <h3>Archivo Literario</h3>
                                <ul class="book-details-list">
                                    <li><strong>Género:</strong> ${libro.genero || 'No especificado'}</li>
                                    <li><strong>Editorial:</strong> ${libro.editorial || 'No especificada'}</li>
                                    <li><strong>Año Original:</strong> ${libro.anio_publicacion || 'Desconocido'}</li>
                                    <li><strong>Páginas:</strong> ${libro.num_paginas || 0}</li>
                                    <li><strong>Palabras:</strong> ${libro.palabras || Math.round((libro.num_paginas || 0) * 250)}</li>
                                </ul>
                                
                                <div class="book-observaciones" style="margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 10px;">
                                    <strong>Contexto / Epílogo:</strong><br>
                                    ${observaciones}
                                </div>

                                <!-- Botón para Editar -->
                                <button class="btn-editar" onclick="prepararEdicion(${libro.id})" style="margin-top: 15px; width: 100%; padding: 8px; background-color: #ff9800; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">
                                    ✏️ Editar Expediente
                                </button>
                            </div>
                                
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
                // BYPASS v3: OpenLibrary con Escaneo Profundo de Metadatos
                const urlOpenLibrary = `https://openlibrary.org/search.json?title=${encodeURIComponent(titulo)}&author=${encodeURIComponent(autor)}`;
                
                const response = await fetch(urlOpenLibrary);
                if (!response.ok) throw new Error("OpenLibrary rechazó la conexión.");
                
                const data = await response.json();

                if (data.docs && data.docs.length > 0) {
                    // Variables vacías para irlas llenando con lo mejor que encontremos
                    let paginas = "";
                    let editorial = "";
                    let isbnLimpio = "";
                    let anio = data.docs[0].first_publish_year || "";

                    // Escaneo profundo: Revisamos los 10 primeros resultados buscando los datos que faltan
                    for (let i = 0; i < Math.min(data.docs.length, 10); i++) {
                        const info = data.docs[i];
                        if (!paginas && info.number_of_pages_median) paginas = info.number_of_pages_median;
                        if (!editorial && info.publisher) editorial = info.publisher[0];
                        if (!isbnLimpio && info.isbn) isbnLimpio = info.isbn[0];
                        
                        // Si ya completamos todo, detenemos el escáner para ahorrar memoria
                        if (paginas && editorial && isbnLimpio) break;
                    }

                    // Rellenar el formulario con los datos fusionados
                    document.getElementById('form-editorial').value = editorial || "Desconocida";
                    document.getElementById('form-anio').value = anio;
                    document.getElementById('form-paginas').value = paginas;
                    document.getElementById('form-palabras').value = paginas ? Math.round(paginas * 250) : "";
                    document.getElementById('form-isbn').value = isbnLimpio || "N/A";
                    document.getElementById('form-resumen').value = "Resumen no disponible en la base de datos libre. (Añadir nota manual aquí).";
                    
                    mensajeInvestigacion.style.color = "#2e7d32"; 
                    mensajeInvestigacion.innerText = "✅ Expediente extraído con Escaneo Profundo.";
                } else {
                    mensajeInvestigacion.style.color = "#d32f2f";
                    mensajeInvestigacion.innerText = "❌ Los archivos de OpenLibrary no tienen este libro.";
                }
            } catch (error) {
                console.error("Error detallado en Bypass v3:", error);
                mensajeInvestigacion.style.color = "#d32f2f";
                mensajeInvestigacion.innerText = `⚠️ Error: ${error.message}`;
            } finally {
                btnAutocompletar.disabled = false;
                btnAutocompletar.style.opacity = "1";
            }
        });
    }
    // =====================================================================
    // 3. MOTOR DE CÁLCULO AUTOMÁTICO DE PALABRAS
    // =====================================================================
    const inputPaginas = document.getElementById('form-paginas');
    const inputPalabras = document.getElementById('form-palabras');

    if (inputPaginas && inputPalabras) {
        inputPaginas.addEventListener('input', (e) => {
            const paginas = parseInt(e.target.value);
            if (!isNaN(paginas) && paginas > 0) {
                inputPalabras.value = paginas * 250; // Estándar editorial
            } else {
                inputPalabras.value = "";
            }
        });
    }
    // =====================================================================
    // 4. LÓGICA DE GUARDADO EN LA BASE DE DATOS
    // =====================================================================
    const btnGuardar = document.getElementById('btn-guardar-libro');
    
    if (btnGuardar) {
        btnGuardar.addEventListener('click', async () => {
            // Recopilamos los datos del formulario
            const libroData = {
                titulo: document.getElementById('form-titulo').value.trim(),
                autor: document.getElementById('form-autor').value.trim(),
                genero: document.getElementById('form-genero').value.trim(),
                anio_publicacion: document.getElementById('form-anio').value,
                isbn: document.getElementById('form-isbn').value.trim(), // ¡Dato agregado!
                editorial: document.getElementById('form-editorial').value.trim(),
                num_paginas: document.getElementById('form-paginas').value,
                palabras: document.getElementById('form-palabras').value,
                observaciones: document.getElementById('form-resumen').value.trim(),
                estado_lectura: "No iniciado", 
                calificacion: 0
            };

            if (!libroData.titulo || !libroData.autor) {
                alert("⚠️ El Título y el Autor son obligatorios para el archivo.");
                return;
            }

            btnGuardar.innerText = "⏳ Guardando...";
            btnGuardar.disabled = true;

            try {
                // Aquí enviaremos los datos a tu servidor Python (FastAPI)
                const response = await fetch('https://bibliotecaria-bot.onrender.com/api/biblioteca/guardar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(libroData)
                });

                const result = await response.json();

                if (response.ok) {
                    alert("✅ ¡Expediente guardado con éxito en la Matriz!");
                    modal.style.display = "none";
                    location.reload(); // Recarga para ver la nueva tarjeta
                } else {
                    alert("❌ Error de la matriz: " + result.detail);
                }
            } catch (error) {
                console.error("Error al guardar:", error);
                alert("⚠️ No se pudo conectar con los servidores centrales.");
            } finally {
                btnGuardar.innerText = "💾 Guardar Expediente en la Matriz";
                btnGuardar.disabled = false;
            }
        });
    }
});
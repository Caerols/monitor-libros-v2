// =====================================================================
// MEMORIA RAM DEL NAVEGADOR (Para poder editar libros sin recargar)
// =====================================================================
window.catalogoGlobal = []; 

window.buscarPortadaAlternativa = async function(imgElement, isbn, titulo, autor) {
    // 1. Apagamos el onerror para evitar un loop infinito si Google también falla
    imgElement.onerror = function() {
        this.style.display = 'none'; // Si falla todo, mostramos fondo azul
    };

    try {
        // Intento 1: Buscar en Google Books por ISBN
        let response = await fetch(`https://www.googleapis.com/books/v1/volumes?q=isbn:${isbn}`);
        let data = await response.json();

        if (data.items && data.items.length > 0 && data.items[0].volumeInfo.imageLinks) {
            // Google devuelve HTTP, forzamos HTTPS
            imgElement.src = data.items[0].volumeInfo.imageLinks.thumbnail.replace('http:', 'https:');
            return;
        }

        // Intento 2: Buscar en Google Books por Título y Autor (Útil para ediciones raras)
        const query = encodeURIComponent(`${titulo} ${autor}`);
        response = await fetch(`https://www.googleapis.com/books/v1/volumes?q=${query}&maxResults=1`);
        data = await response.json();

        if (data.items && data.items.length > 0 && data.items[0].volumeInfo.imageLinks) {
            imgElement.src = data.items[0].volumeInfo.imageLinks.thumbnail.replace('http:', 'https:');
            return;
        }

        // Si Google Books tampoco tiene NADA, ocultamos la imagen
        imgElement.style.display = 'none';

    } catch (error) {
        console.error("Error buscando portada de rescate:", error);
        imgElement.style.display = 'none';
    }
};

document.addEventListener("DOMContentLoaded", () => {
    // =====================================================================
    // 1. MOTOR DE RENDERIZADO DEL CATÁLOGO (FLIP CARDS)
    // =====================================================================
    const API_URL = 'https://bibliotecaria-bot.onrender.com/api/biblioteca/catalogo';
    const contenedorCatalogo = document.getElementById('catalogo-container');

    const formatearDinero = (monto) => {
        if (!monto) return "No registrado";
        return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(monto);
    };

    const obtenerClaseEstado = (estado) => {
        switch(estado) {
            case 'En lectura': return 'en-lectura';
            case 'Finalizado': return 'leido';
            case 'No iniciado': 
            case 'Pendiente': return 'pendiente';
            default: return 'pendiente';
        }
    };

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
            
            // ¡CLAVE! Guardamos los datos en la variable global para poder editarlos luego
            window.catalogoGlobal = catalogo; 
            
            if (!catalogo || catalogo.length === 0) {
                contenedorCatalogo.innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 40px; background: white; border-radius: 12px;">
                        <h3>🗂️ Tu biblioteca está vacía</h3>
                        <p>Aún no has registrado ningún expediente en tu colección personal.</p>
                    </div>`;
                return;
            }

            contenedorCatalogo.innerHTML = '';

            // Generar tarjetas dinámicamente
            catalogo.forEach(libro => {
                const claseEstado = obtenerClaseEstado(libro.estado_lectura);
                const precioTexto = formatearDinero(libro.precio_pagado);
                const estrellas = generarEstrellas(libro.calificacion);
                const observaciones = libro.observaciones ? `<em>"${libro.observaciones}"</em>` : "<em>Sin observaciones.</em>";

                // =========================================================
                // MAGIA DE LAS PORTADAS (OpenLibrary -> Google Books Fallback)
                // =========================================================
                const isbnLimpio = libro.isbn ? String(libro.isbn).replace(/[^0-9X]/gi, '') : '';
                
                let portadaHTML = `
                    <div class="portada-placeholder">
                        <span>${libro.titulo}</span>
                    </div>`;
                
                if (isbnLimpio) {
                    const urlImagen = `https://covers.openlibrary.org/b/isbn/${isbnLimpio}-L.jpg?default=false`;
                    // Escapamos comillas simples en títulos/autores para no romper el HTML
                    const tituloEscapado = libro.titulo.replace(/'/g, "\\'");
                    const autorEscapado = libro.autor.replace(/'/g, "\\'");
                    
                    portadaHTML = `
                        <div class="portada-placeholder" style="position: relative; overflow: hidden; padding: 0;">
                            <!-- Capa 1: Texto de respaldo (siempre al fondo) -->
                            <div style="position: absolute; width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; padding: 15px; box-sizing: border-box; text-align: center;">
                                <span>${libro.titulo}</span>
                            </div>
                            <!-- Capa 2: La imagen real. Cambio clave: object-fit: contain y background blanco -->
                            <img src="${urlImagen}" 
                                 alt="Portada de ${libro.titulo}"
                                 style="width: 100%; height: 100%; object-fit: contain; position: relative; z-index: 10; background-color: #ffffff;"
                                 onerror="buscarPortadaAlternativa(this, '${isbnLimpio}', '${tituloEscapado}', '${autorEscapado}')">
                        </div>
                    `;
                }
                // =========================================================

                const tarjetaHTML = `
                    <div class="book-card">
                        <div class="book-card-inner">
                            
                            <!-- FRENTE -->
                            <div class="book-card-front">
                                ${portadaHTML}
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
                            <div class="book-card-back" style="display: flex; flex-direction: column; height: 100%; max-height: 100%; box-sizing: border-box; overflow: hidden; padding-bottom: 20px;">
                                <h3 style="flex-shrink: 0;">Archivo Literario</h3>
                                <ul class="book-details-list" style="flex-shrink: 0;">
                                    <li><strong>Género:</strong> ${libro.genero || 'No especificado'}</li>
                                    <li><strong>Editorial:</strong> ${libro.editorial || 'No especificada'}</li>
                                    <li><strong>Año Original:</strong> ${libro.anio_publicacion ? (parseInt(libro.anio_publicacion) < 0 ? Math.abs(libro.anio_publicacion) + ' a.C.' : libro.anio_publicacion) : 'Desconocido'}</li>
                                    <li><strong>Páginas:</strong> ${libro.num_paginas || 0}</li>
                                    <li><strong>Palabras:</strong> ${libro.palabras || Math.round((libro.num_paginas || 0) * 250)}</li>
                                </ul>
                                
                                <!-- Caja de texto con Scroll Inteligente -->
                                <div class="book-observaciones" style="flex: 1 1 auto; overflow-y: auto; min-height: 0; margin-top: 10px; border-top: 1px dashed #ccc; padding-top: 10px; margin-bottom: 15px; padding-right: 5px;">
                                    <strong>Contexto / Epílogo:</strong><br>
                                    ${observaciones}
                                </div>

                                <!-- Contenedor de Botones -->
                                <div style="flex-shrink: 0; margin-top: auto;">
                                    <button class="btn-editar" onclick="prepararEdicion(${libro.id})" style="width: 100%; padding: 8px; background-color: #ff9800; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-bottom: 8px;">
                                        ✏️ Editar Expediente
                                    </button>
                                    <button class="btn-eliminar" onclick="eliminarLibro(${libro.id})" style="width: 100%; padding: 8px; background-color: #d32f2f; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">
                                        🗑️ Eliminar Archivo
                                    </button>
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
    // 2. LÓGICA DEL AUTOCOMPLETADO MÁGICO (OPENLIBRARY)
    // =====================================================================
    const btnAutocompletar = document.getElementById('btn-autocompletar');
    const mensajeInvestigacion = document.getElementById('mensaje-investigacion');

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
            mensajeInvestigacion.innerText = "🔍 Interceptando señal de archivos libres... espera.";
            btnAutocompletar.disabled = true;
            btnAutocompletar.style.opacity = "0.7";

            try {
                const urlOpenLibrary = `https://openlibrary.org/search.json?title=${encodeURIComponent(titulo)}&author=${encodeURIComponent(autor)}`;
                const response = await fetch(urlOpenLibrary);
                if (!response.ok) throw new Error("OpenLibrary rechazó la conexión.");
                
                const data = await response.json();

                if (data.docs && data.docs.length > 0) {
                    let paginas = "";
                    let editorial = "";
                    let isbnLimpio = "";
                    let anio = data.docs[0].first_publish_year || "";

                    for (let i = 0; i < Math.min(data.docs.length, 10); i++) {
                        const info = data.docs[i];
                        if (!paginas && info.number_of_pages_median) paginas = info.number_of_pages_median;
                        if (!editorial && info.publisher) editorial = info.publisher[0];
                        if (!isbnLimpio && info.isbn) isbnLimpio = info.isbn[0];
                        if (paginas && editorial && isbnLimpio) break;
                    }

                    document.getElementById('form-editorial').value = editorial || "Desconocida";
                    document.getElementById('form-anio').value = anio;
                    document.getElementById('form-paginas').value = paginas;
                    document.getElementById('form-palabras').value = paginas ? Math.round(paginas * 250) : "";
                    document.getElementById('form-isbn').value = isbnLimpio || "";
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
                inputPalabras.value = paginas * 250; 
            } else {
                inputPalabras.value = "";
            }
        });
    }

    // =====================================================================
    // 4. LÓGICA DE GUARDADO EN LA BASE DE DATOS (CREATE & UPDATE)
    // =====================================================================
    const btnGuardar = document.getElementById('btn-guardar-libro');
    
    if (btnGuardar) {
        btnGuardar.addEventListener('click', async () => {
            const idValue = document.getElementById('form-id').value;
            
            const libroData = {
                // ¡CLAVE! Si hay un ID en el formulario oculto, lo enviamos (Edición). Si no, va como null (Nuevo).
                id: idValue ? parseInt(idValue) : null, 
                titulo: document.getElementById('form-titulo').value.trim(),
                autor: document.getElementById('form-autor').value.trim(),
                genero: document.getElementById('form-genero').value.trim(),
                anio_publicacion: document.getElementById('form-anio').value,
                isbn: document.getElementById('form-isbn').value.trim(), 
                editorial: document.getElementById('form-editorial').value.trim(),
                num_paginas: document.getElementById('form-paginas').value ? parseInt(document.getElementById('form-paginas').value) : 0,
                palabras: document.getElementById('form-palabras').value ? parseInt(document.getElementById('form-palabras').value) : 0,
                observaciones: document.getElementById('form-resumen').value.trim(),
                estado_lectura: document.getElementById('form-estado').value, 
                calificacion: parseInt(document.getElementById('form-calificacion').value) || 0
            };

            if (!libroData.titulo || !libroData.autor) {
                alert("⚠️ El Título y el Autor son obligatorios para el archivo.");
                return;
            }

            btnGuardar.innerText = "⏳ Guardando...";
            btnGuardar.disabled = true;

            try {
                const response = await fetch('https://bibliotecaria-bot.onrender.com/api/biblioteca/guardar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(libroData)
                });

                const result = await response.json();

                if (response.ok && result.exito) {
                    alert("✅ ¡Expediente procesado con éxito en la Matriz!");
                    location.reload(); 
                } else {
                    // Muestra la alerta si es un duplicado o error del servidor
                    alert("❌ Rechazado por la Matriz: " + result.detail);
                }
            } catch (error) {
                console.error("Error al guardar:", error);
                alert("⚠️ No se pudo conectar con los servidores centrales.");
            } finally {
                btnGuardar.innerText = "💾 Guardar Expediente";
                btnGuardar.disabled = false;
            }
        });
    }
});

// =====================================================================
// 5. MOTORES DE EDICIÓN Y ELIMINACIÓN (Globales)
// =====================================================================

window.prepararEdicion = function(id) {
    // 1. Buscamos el libro en la memoria global
    const libro = window.catalogoGlobal.find(l => l.id === id);
    if (!libro) {
        alert("⚠️ No se encontró el expediente en la memoria.");
        return;
    }
    
    // 2. Rellenamos el formulario con los datos existentes
    document.getElementById('form-id').value = libro.id;
    document.getElementById('form-titulo').value = libro.titulo || '';
    document.getElementById('form-autor').value = libro.autor || '';
    document.getElementById('form-genero').value = libro.genero !== 'Sin clasificar' ? libro.genero : '';
    document.getElementById('form-anio').value = libro.anio_publicacion || '';
    document.getElementById('form-editorial').value = libro.editorial || '';
    document.getElementById('form-paginas').value = libro.num_paginas || '';
    document.getElementById('form-palabras').value = libro.palabras || '';
    document.getElementById('form-isbn').value = libro.isbn || '';
    document.getElementById('form-resumen').value = libro.observaciones || '';
    document.getElementById('form-calificacion').value = libro.calificacion || 0;
    document.getElementById('form-estado').value = libro.estado_lectura || 'No iniciado';
    // 3. Cambiamos el texto del botón
    document.getElementById('btn-guardar-libro').innerText = "🔄 Actualizar Expediente";
    
    // 4. Abrimos el modal
    const modal = document.getElementById('modal-ingreso');
    if (modal) {
        modal.style.display = "flex";
    } else {
        alert("⚠️ Error: El contenedor del formulario no existe. Verifica que su ID sea 'modal-ingreso' en el HTML.");
    }
};

window.eliminarLibro = async function(id) {
    if (!confirm("⚠️ ¿Estás seguro de que deseas eliminar este expediente de la Matriz? Esta acción es irreversible.")) return;
    
    try {
        const response = await fetch(`https://bibliotecaria-bot.onrender.com/api/biblioteca/eliminar/${id}`, { 
            method: 'DELETE' 
        });
        
        const result = await response.json();

        if (response.ok && result.exito) {
            alert("🗑️ Expediente eliminado correctamente.");
            location.reload();
        } else {
            alert("❌ Fallo al intentar eliminar el archivo: " + result.detail);
        }
    } catch (e) {
        console.error("Error eliminando:", e);
        alert("⚠️ No se pudo conectar con el servidor para eliminar.");
    }
};
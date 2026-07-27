// =====================================================================
// MEMORIA RAM DEL NAVEGADOR (Para poder editar libros sin recargar)
// =====================================================================
window.catalogoGlobal = []; 

window.buscarPortadaAlternativa = async function(imgElement, isbn, titulo, autor) {
    imgElement.onerror = function() {
        this.style.display = 'none'; 
    };

    try {
        let response = await fetch(`https://www.googleapis.com/books/v1/volumes?q=isbn:${isbn}`);
        let data = await response.json();

        if (data.items && data.items.length > 0 && data.items[0].volumeInfo.imageLinks) {
            imgElement.src = data.items[0].volumeInfo.imageLinks.thumbnail.replace('http:', 'https:');
            return;
        }

        const query = encodeURIComponent(`${titulo} ${autor}`);
        response = await fetch(`https://www.googleapis.com/books/v1/volumes?q=${query}&maxResults=1`);
        data = await response.json();

        if (data.items && data.items.length > 0 && data.items[0].volumeInfo.imageLinks) {
            imgElement.src = data.items[0].volumeInfo.imageLinks.thumbnail.replace('http:', 'https:');
            return;
        }

        imgElement.style.display = 'none';

    } catch (error) {
        console.error("Error buscando portada de rescate:", error);
        imgElement.style.display = 'none';
    }
};

document.addEventListener("DOMContentLoaded", () => {
    // =====================================================================
    // 1. MOTOR DE RENDERIZADO DEL CATÁLOGO (FLIP CARDS - MATRIZ PROFUNDA)
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
        if (!calificacion || calificacion === 0) return "<span style='color: var(--texto-mutado); font-size: 12px;'>Sin calificar</span>";
        let starsHTML = "";
        for (let i = 0; i < calificacion; i++) {
            starsHTML += `<i class="ph-fill ph-star" style="color: var(--neon-ambar); text-shadow: 0 0 5px rgba(245, 158, 11, 0.5);"></i>`;
        }
        return starsHTML;
    };

    fetch(API_URL)
        .then(response => {
            if (!response.ok) throw new Error("Fallo en la comunicación con la matriz central");
            return response.json();
        })
        .then(data => {
            const catalogo = data.catalogo;
            window.catalogoGlobal = catalogo; 
            
            if (!catalogo || catalogo.length === 0) {
                contenedorCatalogo.innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 50px; background: var(--bg-tarjeta); border: 1px dashed var(--borde-fino); border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">
                        <i class="ph ph-folder-dashed" style="font-size: 48px; color: var(--texto-mutado); margin-bottom: 15px; display: block;"></i>
                        <h3 style="color: var(--texto-brillante); margin-bottom: 10px;">Base de datos vacía</h3>
                        <p style="color: var(--texto-mutado);">Aún no has registrado ningún expediente en tu colección personal.</p>
                    </div>`;
                return;
            }

            contenedorCatalogo.innerHTML = '';

            catalogo.forEach(libro => {
                const claseEstado = obtenerClaseEstado(libro.estado_lectura);
                const precioTexto = formatearDinero(libro.precio_pagado);
                const estrellas = generarEstrellas(libro.calificacion);
                const observaciones = libro.observaciones ? `<em style="color: var(--texto-base);">"${libro.observaciones}"</em>` : "<em style='color: var(--texto-mutado);'>Sin anotaciones.</em>";

                // =========================================================
                // CORRECCIÓN: height al 60% para dejar espacio a los textos
                // =========================================================
                const isbnLimpio = libro.isbn ? String(libro.isbn).replace(/[^0-9X]/gi, '') : '';
                
                let portadaHTML = `
                    <div class="portada-placeholder" style="background: var(--bg-input); color: var(--texto-mutado); display: flex; align-items: center; justify-content: center; height: 60%;">
                        <span style="padding: 15px; text-align: center;">${libro.titulo}</span>
                    </div>`;
                
                if (isbnLimpio) {
                    const urlImagen = `https://covers.openlibrary.org/b/isbn/${isbnLimpio}-L.jpg?default=false`;
                    const tituloEscapado = libro.titulo.replace(/'/g, "\\'");
                    const autorEscapado = libro.autor.replace(/'/g, "\\'");
                    
                    portadaHTML = `
                        <div class="portada-placeholder" style="position: relative; overflow: hidden; padding: 0; background: var(--bg-input); height: 60%;">
                            <!-- Capa 1: Texto de respaldo -->
                            <div style="position: absolute; width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; padding: 15px; box-sizing: border-box; text-align: center; color: var(--texto-mutado);">
                                <span>${libro.titulo}</span>
                            </div>
                            <!-- Capa 2: Imagen real -->
                            <img src="${urlImagen}" 
                                 alt="Portada de ${libro.titulo}"
                                 style="width: 100%; height: 100%; object-fit: contain; position: relative; z-index: 10; background-color: var(--bg-abismo);"
                                 onerror="buscarPortadaAlternativa(this, '${isbnLimpio}', '${tituloEscapado}', '${autorEscapado}')">
                        </div>
                    `;
                }

                const tarjetaHTML = `
                    <div class="book-card">
                        <div class="book-card-inner">
                            
                            <!-- FRENTE -->
                            <div class="book-card-front" style="background: var(--bg-tarjeta); border: 1px solid var(--borde-fino); border-top: 2px solid var(--neon-cyan); border-radius: 8px; overflow: hidden;">
                                ${portadaHTML}
                                <div class="book-info-front" style="background: var(--bg-tarjeta); border-top: 1px solid var(--borde-fino);">
                                    <h3 style="color: var(--texto-brillante);">${libro.titulo}</h3>
                                    <p class="autor" style="color: var(--texto-mutado);">${libro.autor}</p>
                                    <div class="book-badges">
                                        <span class="badge badge-estado ${claseEstado}">${libro.estado_lectura}</span>
                                        <span class="badge badge-rating" style="background: rgba(0,0,0,0.3); border: 1px solid var(--borde-fino); padding: 4px 8px; display: flex; align-items: center; gap: 2px;">${estrellas}</span>
                                    </div>
                                </div>
                            </div>

                           <!-- REVERSO -->
                            <div class="book-card-back" style="background: var(--bg-tarjeta); color: var(--texto-base); border: 1px solid var(--borde-fino); border-top: 2px solid var(--neon-cyan); border-radius: 8px; display: flex; flex-direction: column; height: 100%; max-height: 100%; box-sizing: border-box; overflow: hidden; padding: 20px; padding-bottom: 20px;">
                                <h3 style="flex-shrink: 0; color: var(--texto-brillante); border-bottom: 1px solid var(--borde-fino); padding-bottom: 10px; font-size: 15px; text-transform: uppercase; letter-spacing: 1px;">
                                    <i class="ph ph-archive" style="color: var(--neon-cyan); margin-right: 5px;"></i> Archivo Literario
                                </h3>
                                <ul class="book-details-list" style="flex-shrink: 0; padding-top: 10px;">
                                    <li><strong style="color: var(--texto-mutado);">Género:</strong> ${libro.genero || 'No especificado'}</li>
                                    <li><strong style="color: var(--texto-mutado);">Editorial:</strong> ${libro.editorial || 'No especificada'}</li>
                                    <li><strong style="color: var(--texto-mutado);">Año Original:</strong> ${libro.anio_publicacion ? (parseInt(libro.anio_publicacion) < 0 ? Math.abs(libro.anio_publicacion) + ' a.C.' : libro.anio_publicacion) : 'Desconocido'}</li>
                                    <li><strong style="color: var(--texto-mutado);">Páginas:</strong> ${libro.num_paginas || 0}</li>
                                    <li><strong style="color: var(--texto-mutado);">Palabras:</strong> ${libro.palabras || Math.round((libro.num_paginas || 0) * 250)}</li>
                                </ul>
                                
                                <div class="book-observaciones" style="flex: 1 1 auto; overflow-y: auto; min-height: 0; margin-top: 10px; border-top: 1px dashed var(--borde-fino); padding-top: 10px; margin-bottom: 15px; padding-right: 5px; font-size: 13px;">
                                    <strong style="color: var(--texto-mutado);">Contexto / Epílogo:</strong><br>
                                    ${observaciones}
                                </div>

                                <div style="flex-shrink: 0; margin-top: auto;">
                                    <button class="btn-editar" onclick="prepararEdicion(${libro.id})" style="width: 100%; padding: 10px; background-color: rgba(245, 158, 11, 0.1); color: var(--neon-ambar); border: 1px solid var(--neon-ambar); border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 8px; transition: background 0.3s;">
                                        <i class="ph ph-pencil-simple" style="margin-right: 5px;"></i> Editar Expediente
                                    </button>
                                    <button class="btn-eliminar" onclick="eliminarLibro(${libro.id})" style="width: 100%; padding: 10px; background-color: rgba(239, 68, 68, 0.1); color: var(--neon-rojo); border: 1px solid var(--neon-rojo); border-radius: 6px; cursor: pointer; font-weight: 600; transition: background 0.3s;">
                                        <i class="ph ph-trash" style="margin-right: 5px;"></i> Eliminar Archivo
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
                    <div style="grid-column: 1 / -1; color: var(--neon-rojo); text-align: center; padding: 20px; background: rgba(239, 68, 68, 0.1); border: 1px solid var(--neon-rojo); border-radius: 8px;">
                        <i class="ph ph-warning-circle" style="font-size: 24px; margin-bottom: 10px; display: block;"></i>
                        Error de conexión con la base de datos de la Bibliotecaria.
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
                mensajeInvestigacion.style.color = "var(--neon-rojo)"; 
                mensajeInvestigacion.innerHTML = "<i class='ph ph-warning'></i> Necesito el título y el autor para iniciar la búsqueda.";
                return;
            }

            mensajeInvestigacion.style.color = "var(--neon-azul)"; 
            mensajeInvestigacion.innerHTML = "<i class='ph ph-spinner ph-spin'></i> Interceptando señal de archivos libres...";
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
                    
                    mensajeInvestigacion.style.color = "var(--neon-verde)"; 
                    mensajeInvestigacion.innerHTML = "<i class='ph ph-check-circle'></i> Expediente extraído con Escaneo Profundo.";
                } else {
                    mensajeInvestigacion.style.color = "var(--neon-rojo)";
                    mensajeInvestigacion.innerHTML = "<i class='ph ph-x-circle'></i> Los archivos de OpenLibrary no tienen este libro.";
                }
            } catch (error) {
                console.error("Error detallado en Bypass v3:", error);
                mensajeInvestigacion.style.color = "var(--neon-rojo)";
                mensajeInvestigacion.innerHTML = `<i class='ph ph-warning'></i> Error: ${error.message}`;
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

            btnGuardar.innerHTML = "<i class='ph ph-spinner-gap ph-spin' style='margin-right: 8px;'></i> Procesando...";
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
                    alert("❌ Rechazado por la Matriz: " + result.detail);
                }
            } catch (error) {
                console.error("Error al guardar:", error);
                alert("⚠️ No se pudo conectar con los servidores centrales.");
            } finally {
                btnGuardar.innerHTML = "<i class='ph ph-floppy-disk' style='margin-right: 8px;'></i> Guardar Expediente";
                btnGuardar.disabled = false;
            }
        });
    }
});

// =====================================================================
// 5. MOTORES DE EDICIÓN Y ELIMINACIÓN (Globales)
// =====================================================================

window.prepararEdicion = function(id) {
    const libro = window.catalogoGlobal.find(l => l.id === id);
    if (!libro) {
        alert("⚠️ No se encontró el expediente en la memoria.");
        return;
    }
    
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
    
    document.getElementById('btn-guardar-libro').innerHTML = "<i class='ph ph-arrows-clockwise' style='margin-right: 8px;'></i> Actualizar Expediente";
    
    const modal = document.getElementById('modal-ingreso');
    if (modal) {
        modal.style.display = "flex";
    } else {
        alert("⚠️ Error: El contenedor del formulario no existe.");
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
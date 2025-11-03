def mostrar_prospectos(df_prospectos, df_polizas):
    st.header("Gestión de Prospectos")

    # Inicializar estado para la edición
    if 'modo_edicion' not in st.session_state:
        st.session_state.modo_edicion = False
    if 'prospecto_editando' not in st.session_state:
        st.session_state.prospecto_editando = None
    if 'prospecto_data' not in st.session_state:
        st.session_state.prospecto_data = {}

    # Selector para editar prospecto existente
    if not df_prospectos.empty:
        prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
        # Incluimos una opción vacía para no seleccionar nada
        prospecto_seleccionado = st.selectbox(
            "Seleccionar Prospecto para editar", 
            [""] + prospectos_lista, 
            key="editar_prospecto"
        )

        # Cuando se selecciona un prospecto, cargar sus datos
        if prospecto_seleccionado and st.session_state.prospecto_editando != prospecto_seleccionado:
            st.session_state.prospecto_editando = prospecto_seleccionado
            st.session_state.modo_edicion = True
            # Cargar datos del prospecto seleccionado
            prospecto_data = df_prospectos[df_prospectos["Nombre/Razón Social"] == prospecto_seleccionado].iloc[0]
            st.session_state.prospecto_data = prospecto_data.to_dict()
            st.rerun()
        elif not prospecto_seleccionado and st.session_state.modo_edicion:
            # Si se deselecciona, limpiar el estado
            st.session_state.modo_edicion = False
            st.session_state.prospecto_editando = None
            st.session_state.prospecto_data = {}
            st.rerun()

        # Usar datos almacenados en session_state
        prospecto_data = st.session_state.prospecto_data
    else:
        prospecto_data = {}
        st.session_state.modo_edicion = False
        st.session_state.prospecto_editando = None
        st.session_state.prospecto_data = {}

    # Si estamos en modo edición, mostrar botón para cancelar
    if st.session_state.modo_edicion:
        if st.button("❌ Cancelar Edición"):
            st.session_state.modo_edicion = False
            st.session_state.prospecto_editando = None
            st.session_state.prospecto_data = {}
            st.rerun()

    with st.form("form_prospectos", clear_on_submit=not st.session_state.modo_edicion):
        col1, col2 = st.columns(2)

        with col1:
            # Siempre mostrar campos con valores actuales (vacíos si no hay datos)
            tipo_persona = st.selectbox(
                "Tipo Persona", 
                OPCIONES_PERSONA,
                index=OPCIONES_PERSONA.index(prospecto_data.get("Tipo Persona", OPCIONES_PERSONA[0])) 
                if prospecto_data.get("Tipo Persona") in OPCIONES_PERSONA else 0,
                key="prospecto_tipo"
            )
            
            nombre_razon = st.text_input(
                "Nombre/Razón Social*", 
                value=prospecto_data.get("Nombre/Razón Social", ""), 
                key="prospecto_nombre"
            )
            
            fecha_nacimiento = st.text_input(
                "Fecha Nacimiento (dd/mm/yyyy)", 
                value=prospecto_data.get("Fecha Nacimiento", ""),
                placeholder="dd/mm/yyyy",
                key="prospecto_nacimiento"
            )
            
            rfc = st.text_input(
                "RFC", 
                value=prospecto_data.get("RFC", ""), 
                key="prospecto_rfc"
            )
            
            telefono = st.text_input(
                "Teléfono", 
                value=prospecto_data.get("Teléfono", ""), 
                key="prospecto_telefono"
            )
            
            correo = st.text_input(
                "Correo", 
                value=prospecto_data.get("Correo", ""), 
                key="prospecto_correo"
            )
            
            direccion = st.text_input(
                "Dirección", 
                value=prospecto_data.get("Dirección", ""),
                placeholder="Ej: Calle 123, CDMX, 03100",
                key="prospecto_direccion"
            )

        with col2:
            producto = st.selectbox(
                "Producto", 
                OPCIONES_PRODUCTO,
                index=OPCIONES_PRODUCTO.index(prospecto_data.get("Producto", OPCIONES_PRODUCTO[0])) 
                if prospecto_data.get("Producto") in OPCIONES_PRODUCTO else 0,
                key="prospecto_producto"
            )
            
            fecha_registro = st.text_input(
                "Fecha Registro*", 
                value=prospecto_data.get("Fecha Registro", fecha_actual()),
                placeholder="dd/mm/yyyy",
                key="prospecto_registro"
            )
            
            fecha_contacto = st.text_input(
                "Fecha Contacto (dd/mm/yyyy)", 
                value=prospecto_data.get("Fecha Contacto", ""),
                placeholder="dd/mm/yyyy",
                key="prospecto_contacto"
            )
            
            seguimiento = st.text_input(
                "Seguimiento (dd/mm/yyyy)", 
                value=prospecto_data.get("Seguimiento", ""),
                placeholder="dd/mm/yyyy",
                key="prospecto_seguimiento"
            )
            
            representantes = st.text_area(
                "Representantes Legales (separar por comas)", 
                value=prospecto_data.get("Representantes Legales", ""),
                placeholder="Ej: Juan Pérez, María García",
                key="prospecto_representantes"
            )
            
            referenciador = st.text_input(
                "Referenciador", 
                value=prospecto_data.get("Referenciador", ""),
                placeholder="Origen del cliente/promoción",
                key="prospecto_referenciador"
            )

        # Validar fechas
        fecha_errors = []
        if fecha_nacimiento:
            valido, error = validar_fecha(fecha_nacimiento)
            if not valido:
                fecha_errors.append(f"Fecha Nacimiento: {error}")

        if fecha_registro:
            valido, error = validar_fecha(fecha_registro)
            if not valido:
                fecha_errors.append(f"Fecha Registro: {error}")

        if fecha_contacto:
            valido, error = validar_fecha(fecha_contacto)
            if not valido:
                fecha_errors.append(f"Fecha Contacto: {error}")

        if seguimiento:
            valido, error = validar_fecha(seguimiento)
            if not valido:
                fecha_errors.append(f"Seguimiento: {error}")

        if fecha_errors:
            for error in fecha_errors:
                st.error(error)

        # Botones de acción
        col_b1, col_b2 = st.columns(2)

        with col_b1:
            if st.session_state.modo_edicion:
                submitted = st.form_submit_button("💾 Actualizar Prospecto")
            else:
                submitted = st.form_submit_button("💾 Agregar Nuevo Prospecto")

        if submitted:
            if not nombre_razon:
                st.warning("Debe completar al menos el nombre o razón social")
            elif fecha_errors:
                st.warning("Corrija los errores en las fechas antes de guardar")
            else:
                nuevo_prospecto = {
                    "Tipo Persona": tipo_persona,
                    "Nombre/Razón Social": nombre_razon,
                    "Fecha Nacimiento": fecha_nacimiento if fecha_nacimiento else "",
                    "RFC": rfc,
                    "Teléfono": telefono,
                    "Correo": correo,
                    "Dirección": direccion,
                    "Producto": producto,
                    "Fecha Registro": fecha_registro if fecha_registro else fecha_actual(),
                    "Fecha Contacto": fecha_contacto if fecha_contacto else "",
                    "Seguimiento": seguimiento if seguimiento else "",
                    "Representantes Legales": representantes,
                    "Referenciador": referenciador
                }

                if st.session_state.modo_edicion:
                    # Actualizar prospecto existente
                    index = df_prospectos[df_prospectos["Nombre/Razón Social"] == st.session_state.prospecto_editando].index
                    for key, value in nuevo_prospecto.items():
                        df_prospectos.loc[index, key] = value
                    mensaje = "✅ Prospecto actualizado correctamente"

                    # Salir del modo edición después de guardar
                    st.session_state.modo_edicion = False
                    st.session_state.prospecto_editando = None
                    st.session_state.prospecto_data = {}
                else:
                    # Agregar nuevo prospecto
                    df_prospectos = pd.concat([df_prospectos, pd.DataFrame([nuevo_prospecto])], ignore_index=True)
                    mensaje = "✅ Prospecto agregado correctamente"

                if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas):
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error("❌ Error al guardar el prospecto")

    # Mostrar lista de prospectos
    st.subheader("Lista de Prospectos")
    if not df_prospectos.empty:
        st.dataframe(df_prospectos, use_container_width=True)
    else:
        st.info("No hay prospectos registrados")

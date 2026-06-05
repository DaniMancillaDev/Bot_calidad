Twitter
Inicio
Preguntas frecuentes
Aplicaciones
API
Protocolo
Esquema
Cambios recientes
Diseño de mini aplicaciones
Implementación de mini aplicaciones
Inicializando mini aplicaciones
Probando mini aplicaciones
Uso de bots en el entorno de prueba
Modo de depuración para mini aplicaciones
BotsMini aplicaciones de Telegram
Mini aplicaciones de Telegram
Con Mini aplicaciones Los desarrolladores pueden utilizar JavaScript crear Interfaces infinitamente flexibles que se puede lanzar directamente dentro de Telegram — y puede reemplazar por completo cualquier sitio web.

Como bots, Mini aplicaciones soporte autorización perfecta, pagos a través de terceros proveedores de pagos (con Pago de Google y Pago de Apple listo para usar), entregando notificaciones push personalizadas a los usuarios y mucho más.

Para ver un Mini aplicación En acción, prueba nuestra muestra @DurgerKingBot.

Cambios recientes
3 de abril de 2026
Se agregó el método solicitudChat a la clase Aplicación web.
1 de marzo de 2026
API de bots 9.5

Se agregó el campo iconCustomEmojiId a la clase Botón inferior.
3 de julio de 2025
API de bots 9.1

Se agregó el método ocultarTeclado a la clase Aplicación web.
11 de abril de 2025
API de bots 9.0

Se agregó el campo Almacenamiento de dispositivos, permitiendo que las Mini Aplicaciones utilicen almacenamiento local persistente en el dispositivo del usuario.
Se agregó el campo Almacenamiento seguro, permitiendo que las Mini Aplicaciones utilicen un almacenamiento local seguro en el dispositivo del usuario para datos confidenciales.
17 de noviembre de 2024
API de bots 8.0

Este es el actualización más grande en la historia de las mini aplicaciones de Telegram – agregando más de 10 nuevas funciones y opciones de monetización para desarrolladores. Para leer más sobre todos estos cambios, consulte esto publicación de blog dedicada.

Modo de pantalla completa

Las mini aplicaciones ahora pueden hacerlo llegar a pantalla completa tanto en retrato como modo paisaje – permitiéndoles hospedar Más juegos, juega medios de pantalla ancha y apoyo inmersivo experiencias de usuario.
Se agregaron los métodos solicitudPantalla completa y salirPantalla completa para alternar el modo de pantalla completa.
Se agregaron los campos Inserción de área segura y contenidoSafeAreaInset, lo que permite a las Mini Aplicaciones garantizar que su contenido respete adecuadamente los márgenes del área segura del dispositivo.
Además se agregaron los campos está activo y es Pantalla completa a la clase Aplicación web.
Se agregó el eventos activado, desactivado, Área segura cambiada, contenidoÁrea seguraCambiada, pantalla completaCambiado y pantalla completaFalló.
Atajos de pantalla de inicio

Ahora se puede acceder a las mini aplicaciones a través de atajos directos añadido al pantalla de inicio de dispositivos móviles.
Se agregó el método agregar a la pantalla de inicio para crear un acceso directo para que los usuarios lo agreguen a sus pantallas de inicio.
Se agregó el método comprobar el estado de la pantalla de inicio para determinar el estado y la compatibilidad del acceso directo a la pantalla de inicio de la Mini Aplicación en el dispositivo actual.
Se agregó el eventos InicioPantallaAñadida y pantalla de inicio comprobada.
Estado del emoji

Las mini aplicaciones ahora pueden solicitar a los usuarios que configuren sus estado del emoji – o solicitar acceso para luego sincronizarlo automáticamente con insignias del juego, API de terceros y más.
Se agregó el método establecerEstadoEmoji para permitir a los usuarios confirmar manualmente un emoji personalizado como su nuevo estado a través de un cuadro de diálogo nativo.
Se agregó el método solicitudEmojiStatusAccess para obtener permiso para actualizar posteriormente el estado del emoji de un usuario a través del método Bot API setUserEmojiStatus.
Se agregó el eventos conjunto de estados emoji, Estado del emoji fallido y emojiStatusAccessSolicitado.
Intercambio de medios y descargas de archivos

Los usuarios ahora pueden hacerlo compartir medios directamente desde Mini Apps – enviando códigos de referencia, memes personalizados, ilustraciones y más cualquier chat o publicarlos como una historia.
Se agregó el método compartir mensaje para compartir medios desde Mini Apps hasta chats de Telegram. Ver también Mensaje preparado en línea.
Se agregó el método descargar archivo, introduciendo apoyo para a ventana emergente nativa que solicita a los usuarios que descarguen archivos desde la Mini App.
Se agregó el eventos compartirMensajeEnviado, mensaje compartido fallido y archivoDescargadoSolicitado.
Acceso a geolocalización

Las mini aplicaciones ahora pueden solicitar acceso a geolocalización a los usuarios, permitiéndoles crear prácticamente cualquier servicio basado en la ubicación, desde juegos con puntos de interés dinámicos para mapas interactivos para eventos.
Se agregó el campo Administrador de ubicación a la clase Aplicación web.
Se agregó el eventos administrador de ubicación actualizado y UbicaciónSolicitada.
Seguimiento del movimiento del dispositivo

Las mini aplicaciones ahora pueden rastrear detalles datos de movimiento del dispositivo, permitiéndoles implementar mejores herramientas de productividad, inmersivas Experiencias de realidad virtual y más.
Se agregaron los campos isOrientationLocked, Acelerómetro, Orientación del dispositivo y Giroscopio a la clase Aplicación web.
Se agregaron los métodos lockOrientation y desbloquearOrientación para controlar la orientación de la pantalla.
Se agregó el eventos acelerómetroArrancado, acelerómetro detenido, acelerómetro cambiado, El acelerómetro falló, Se inició la orientación del dispositivo, Orientación del dispositivo detenida, Orientación del dispositivoCambiada, Error en la orientación del dispositivo, giroscopioIniciado, giroscopio detenido, giroscopio cambiado, El giroscopio falló.
Planes de suscripción y regalos para Telegram Stars

Las mini aplicaciones ahora son compatibles suscripciones pagas Desarrollado por Estrellas de Telegram – monetizando sus esfuerzos con múltiples niveles de contenido y características.
Las mini aplicaciones pueden utilizar su saldo de Estrellas de Telegram to enviar regalos a sus usuarios.
Puede leer más sobre la implementación de suscripciones y regalos pagos en nuestro Documentación de la API del bot.
Personalización de la pantalla de carga

Las mini aplicaciones pueden personalizar su pantalla de carga y agregar su propio icono y colores específicos para temas claros y oscuros.
Puede acceder a estas configuraciones de personalización en @BotFather via /mybots > Seleccionar bot > Configuración del bot > Configurar miniaplicación > Habilitar miniaplicación
Optimizaciones específicas de hardware

Las mini aplicaciones que se ejecutan en Android ahora pueden recibir información básica sobre el hardware de procesamiento de un dispositivo, permitiéndoles optimizar la experiencia del usuario basado en las capacidades del dispositivo.
Esta información incluye las respectivas versiones del sistema operativo, la aplicación y el SDK, así como el modelo y la clase de rendimiento del dispositivo.
General

El campo foto_url en la clase Usuario de aplicación web ahora está disponible para todas las Mini Aplicaciones, lo que les permite acceder a la foto de perfil de un usuario si su configuración de privacidad lo permite.
Los terceros (por ejemplo, creadores de mini aplicaciones, SDK externos, etc.) que reciben o procesan datos en nombre de las mini aplicaciones ahora pueden hacerlo validarlo sin conocer la aplicación token de bot.
Depuración opciones se han ampliado para incluir apoyo total Dispositivos iOS. Puede utilizar estas herramientas para encontrar problemas específicos de la aplicación en su Mini App.
6 de septiembre de 2024
API de bots 7.10

Se agregó el campo Botón secundario a la clase Aplicación web.
Se agregó el evento Botón secundarioSe hizo clic.
Cambió el nombre de la clase Botón principal a la clase Botón inferior.
Se agregó el campo color de la barra inferior y el método establecer color de barra inferior a la clase Aplicación web.
Se agregó el campo color_barra_bg_inferior a la clase Parámetros temáticos.
31 de julio de 2024
API de bots 7.8

Se agregó la opción para que los bots establezcan un Mini aplicación principal, que se puede previsualizar y ejecutar directamente desde un botón en el perfil del bot o un enlace.
Se agregó el método compartir con la historia a la clase Aplicación web.
7 de julio de 2024
API de bots 7.7

Se agregó el campo isVerticalSwipes habilitado y los métodos habilitar deslizamientos verticales, Deshabilitar deslizamientos verticales a la clase Aplicación web.
Se agregó el evento scanQrPopupCerrado.
1 de julio de 2024
API de bots 7.6

Se agregó el campo sección_separador_color a la clase Parámetros temáticos.
Se cambió el modo de apertura predeterminado para Mini aplicaciones de enlace directo.
31 de marzo de 2024
API de bots 7.2

Se agregó el campo Gerente Biométrico a la clase Aplicación web.
29 de diciembre de 2023
API de bots 7.0

Se agregó el campo Botón de configuración a la clase Aplicación web.
Se agregaron los campos encabezado_bg_color, acento_texto_color, sección_bg_color, sección_encabezado_texto_color, subtítulo_texto_color, color_texto_destructivo a la clase Parámetros temáticos.
Las mini aplicaciones ya no se cierran cuando el método Aplicación web.openTelegramLink se llama.
22 de septiembre de 2023
API de bots 6.9

Se agregó el campo Almacenamiento en la nube a la clase Aplicación web.
Se agregaron los métodos solicitudEscribirAcceso y solicitudContacto a la clase Aplicación web.
Se agregaron los campos agregado_al_menú_adjunto y permite_escribir_en_pm a la clase Usuario de aplicación web.
Se agregaron los eventos writeAccessSolicitado y contactoSolicitado.
Se agregó la capacidad de configurar cualquier color de encabezado usando el establecer color de encabezado método.
21 de abril de 2023
API de bots 6.7

Se agregó soporte para iniciar Mini Apps desde los resultados de consultas en línea y desde un enlace directo.
Se agregó el método switchInlineQuery a la clase Aplicación web.
30 de diciembre de 2022
API de bots 6.4

Se agregó el campo plataforma, el parámetro opcional opciones al método enlace abierto y los métodos mostrarScanQrPopup, cerrarScanQrPopup, leer texto desde el portapapeles a la clase Aplicación web.
Se agregaron los eventos qrTextoRecibido, texto del portapapeles recibido.
12 de agosto de 2022
API de bots 6.2

Se agregó el campo isClosingConfirmationHabilitado y los métodos habilitarConfirmación de cierre, deshabilitarConfirmación de cierre, showPopup, mostrarAlerta, showConfirmar a la clase Aplicación web.
Se agregó el campo es_premium a la clase Usuario de aplicación web.
Se agregó el evento popupCerrado.
20 de junio de 2022
API de bots 6.1

Se agregó la capacidad de usar bots agregados al menú de archivos adjuntos en chats grupales, de supergrupos y de canales.
Se agregó soporte para enlaces t.me que se puede utilizar para seleccionar el chat en el que se abrirá el menú adjunto con el bot.
Se agregaron los campos versión, color del encabezado, color de fondo, Botón de retroceso, Comentarios hápticos y los métodos esVersiónAlMínimo, establecer color de encabezado, establecerColorDeFondo, enlace abierto, enlace de openTelegram, abrir factura a la clase Aplicación web.
Se agregó el campo secundario_bg_color a la clase Parámetros temáticos.
Se agregó el método offClick a la clase Botón principal.
Se agregaron los campos chat, puede_enviar_después a la clase Datos de entrada de la aplicación web.
Se agregó el eventos Botón AtrásSe hizo clic, botón de configuraciónSe hizo clic, facturaCerrada.
Diseño de mini aplicaciones
Esquemas de colores
Las mini aplicaciones siempre reciben datos sobre la situación actual del usuario tema de color en tiempo real, para que puedas ajustar la apariencia de tus interfaces para que coincida con ella. Por ejemplo, cuando los usuarios cambian entre Día y noche modos o utilizar varios temas personalizados.

Saltar a información técnica

Pautas de diseño
Las aplicaciones de Telegram son conocidas por ser ágiles, fluidas y seguir un diseño multiplataforma consistente. Lo ideal es que su mini aplicación refleje estos principios.

Todos los elementos deben ser responsivos y estar diseñados con un enfoque móvil primero.
Los elementos interactivos deben imitar el estilo, el comportamiento y la intención de los componentes de la interfaz de usuario que ya existen.
Todas las animaciones incluidas deben ser fluidas, idealmente de 60 fps.
Todas las entradas e imágenes deben contener etiquetas para fines de accesibilidad.
La aplicación debe ofrecer una experiencia fluida al monitorear el colores dinámicos basados en temas proporcionados por la API y utilizándolos en consecuencia.
Asegúrese de que la interfaz de la aplicación respete el zona segura y Área segura de contenido para evitar superposiciones con elementos de control, especialmente cuando se utiliza el modo de pantalla completa.
Para dispositivos Android, considere la información adicional en el Agente de usuario (ver Detalles del agente de usuario) y ajustar la clase de rendimiento del dispositivo, minimizando las animaciones y los efectos visuales en dispositivos de bajo rendimiento para garantizar un rendimiento fluido.
Implementación de mini aplicaciones
Actualmente, Telegram admite siete formas diferentes de iniciar Mini Apps: la Mini App principal desde a botón de perfil, de a botón del teclado, de un botón en línea, desde el botón de menú del bot, vía modo en línea, de a enlace directo – e incluso desde el menú adjunto.

Tipos de botones
Mini aplicaciones de botones de teclado
TL;DR: Mini aplicaciones lanzadas desde a aplicación web tipo botón del teclado Puede enviar datos de vuelta al bot en un mensaje de servicio usando Telegram.WebApp.enviar datos. Esto hace posible que el bot produzca una respuesta sin comunicarse con ningún servidor externo.

Los usuarios pueden interactuar con bots usando teclados personalizados, Botones debajo de los mensajes del bot, así como enviando forma libre mensajes de texto o cualquiera de los tipos de archivos adjuntos compatible con Telegram: fotos y vídeos, archivos, ubicaciones, contactos y encuestas. Para una mayor flexibilidad aún, los bots pueden utilizar todo el poder de HTML5 para crear interfaces de entrada fáciles de usar.

Puedes enviar un aplicación web tipo Botón del teclado que abre una Mini Aplicación desde la URL especificada.

Para transmitir datos del usuario al bot, la Mini Aplicación puede llamar al Telegram.WebApp.enviar datos método. Los datos se transmitirán al bot como una cadena en un mensaje de servicio. El bot puede continuar comunicándose con el usuario después de recibirlo.

Bueno para:

Interfaces de entrada de datos personalizadas (un calendario personalizado para seleccionar fechas; seleccionar datos de una lista con opciones de búsqueda avanzadas; un aleatorizador que permite al usuario “girar una rueda” y elegir una de las opciones disponibles, etc.)
Componentes reutilizables que no dependen de un bot en particular.
Mini aplicaciones con botones en línea
TL;DR: Para miniaplicaciones más interactivas como @DurgerKingBot, usa un aplicación web tipo Botón de teclado en línea, que obtiene información básica del usuario y puede usarse para enviar un mensaje en nombre del usuario al chat con el bot.

Si recibir datos de texto por sí solo no es suficiente o necesita una interfaz más avanzada y personalizada, puede abrir una Mini App usando a aplicación web tipo Botón de teclado en línea.

Desde el botón se abrirá una Mini App con la URL especificada en el botón. Además de los del usuario configuración del tema, recibirá información básica del usuario (ID, name, username, language_code) y un identificador único para la sesión, consulta_id, que permite enviar mensajes en nombre del usuario al bot.

El bot puede llamar al método API del bot respuestaWebAppQuery para enviar un mensaje en línea del usuario al bot y cerrar la Mini App. Después de recibir el mensaje, el bot puede seguir comunicándose con el usuario.

Bueno para:

Servicios web completos e integraciones de cualquier tipo.
Los casos de uso son efectivos ilimitado.
Iniciar miniaplicaciones desde el botón Menú
TL;DR: Las mini aplicaciones se pueden iniciar desde un botón de menú personalizado. Esto simplemente ofrece una forma más rápida de acceder a la aplicación y es diferente idéntico to Iniciar una mini aplicación desde un botón en línea.

De forma predeterminada, los chats con bots siempre muestran una conveniencia botón de menú que proporciona acceso rápido a todos los listados comandos. Con API de bots 6.0, este botón se puede utilizar para lanza una mini aplicación en cambio.

Para configurar el botón de menú, debes especificar el texto que debe mostrar y la URL de la Mini Aplicación. Hay dos formas de establecer estos parámetros:

Para personalizar el botón para Todos los usuarios, uso @BotFather (el /setmenubutton comando o Configuración del bot > Botón de menú).
Para personalizar el botón para ambos Todos los usuarios y usuarios específicos, utiliza el botón de menú setChat método en la API de Bot. Por ejemplo, cambie el texto del botón según el idioma del usuario o muestre enlaces a diferentes Mini Aplicaciones según la configuración del usuario en su bot.
Aparte de esto, las mini aplicaciones abiertas a través del botón de menú funcionan exactamente de la misma manera que cuando usando botones en línea.

@DurgerKingBot permite iniciar su Mini App tanto desde un botón en línea como desde el botón de menú.

Lanzamiento de la mini aplicación principal
TL;DR: Si tu bot es una mini aplicación, puedes agregar una destacada Iniciar aplicación botón, así como videos de demostración y capturas de pantalla de alta calidad en el perfil del bot. Para hacer esto, vaya a @BotFather y configura tu bot Mini aplicación principal.

Si tu bot es una mini aplicación, puedes desbloquear una serie de funciones que agilizan y simplifican la forma en que los usuarios lo ven e interactúan con él. Para hacer esto, vaya a @BotFather y configura tu bot Mini aplicación principal.

Después de configurar una mini aplicación principal, podrás cargar información detallada Demostraciones de vista previa de medios para resaltar públicamente las características clave de su aplicación en su perfil. A Iniciar aplicación También aparecerá un botón que permitirá a los usuarios abrir su aplicación directamente desde su perfil. Los bots que habilitaron una mini aplicación principal se mostrarán en el Aplicaciones pestaña de la búsqueda de usuarios que los han lanzado.

Soporte de vistas previas de medios varios idiomas – para que puedas subir versiones traducidas de sus vistas previas que se mostrarán a los usuarios en función de sus idioma de la aplicación.

Un bot Mini aplicación principal También se puede abrir en el chat actual mediante un enlace directo en el formato https://t.me/botusername?startapp. Si no está vacío aplicación inicial El parámetro está incluido en el enlace, se pasará a la Mini App en el start_param campo y en el parámetro GET tgWebAppStartParam.

Ejemplos

https://t.me/botusername?startapp
https://t.me/botusername?startapp=command
https://t.me/botusername?startapp=command&mode=compact

En este modo, las Mini Aplicaciones pueden utilizar el tipo_chat y chat_instancia parámetros para realizar un seguimiento del contexto de chat actual. Esto introduce soporte para concurrente y compartido uso por parte de varios miembros del chat – para crear pizarras en vivo, órdenes grupales, juegos multijugador y aplicaciones similares.

De forma predeterminada, la miniaplicación principal se abre a la altura de pantalla completa y los usuarios no pueden reducirla a la mitad de la altura. Sin embargo, puedes cambiar este comportamiento mediante @BotFather o incluyendo el parámetro mode=compact en el enlace a la Mini App, en cuyo caso se abrirá a media altura de pantalla de forma predeterminada.

Bueno para:

Servicios web completos e integraciones que cualquier usuario puede abrir con un solo toque.
Servicios cooperativos, multijugador u orientados al trabajo en equipo dentro de un contexto de chat.
Los casos de uso son efectivos ilimitado.
Bots exitosos que enable una mini aplicación principal y aceptar pagos en Estrellas de Telegram Puede aparecer en Telegram Mini App Store. Para aumentar las posibilidades de aparecer, recomendamos cargar contenido multimedia de alta calidad que muestre su aplicación en el perfil de su bot y seguir nuestras instrucciones pautas de diseño.

Mini aplicaciones en modo en línea
TL;DR: Mini aplicaciones lanzadas vía aplicación web tipo Botón de resultados de consulta en línea Se puede utilizar en cualquier lugar en modo en línea. Los usuarios pueden crear contenido en una interfaz web y luego enviarlo sin problemas al chat actual a través del modo en línea.

Puedes utilizar el botón parámetro en el respuestaConsulta en línea método para mostrar un botón especial 'Cambiar a Mini App' encima o en lugar de los resultados en línea. Este botón lo hará abre una mini aplicación desde la URL especificada. Una vez hecho esto, puedes llamar al Consulta en línea de Telegram.WebApp.switch método para enviar al usuario nuevamente al modo en línea.

Las mini aplicaciones en línea tienen Sin acceso al chat – no pueden leer mensajes ni enviar otros nuevos en nombre del usuario. Para enviar mensajes, el usuario debe ser redirigido a modo en línea y elegir activamente un resultado.

Bueno para:

Servicios web completos e integraciones en modo en línea.
Mini aplicaciones de enlace directo
TL;DR: Los Mini App Bots se pueden iniciar desde un enlace directo en cualquier chat. Apoyan a aplicación inicial parámetro y conocen el contexto de chat actual.

Puede utilizar enlaces directos a abre una mini aplicación directamente en el chat actual. Si no está vacío aplicación inicial El parámetro está incluido en el enlace, se pasará a la Mini App en el start_param campo y en el parámetro GET tgWebAppStartParam.

En este modo, las Mini Aplicaciones pueden utilizar el tipo_chat y chat_instancia parámetros para realizar un seguimiento del contexto de chat actual. Esto introduce soporte para concurrente y compartido uso por parte de varios miembros del chat – para crear pizarras en vivo, órdenes grupales, juegos multijugador y aplicaciones similares.

Las mini aplicaciones abiertas desde un enlace directo tienen Sin acceso al chat – no pueden leer mensajes ni enviar otros nuevos en nombre del usuario. Para enviar mensajes, el usuario debe ser redirigido a modo en línea y elegir activamente un resultado.

Empezando desde API de bots 7.6, de forma predeterminada, las mini aplicaciones de este tipo se abren a la altura de pantalla completa y los usuarios no pueden reducirlas a la mitad de la altura. Sin embargo, puedes cambiar este comportamiento incluyendo el parámetro mode=compact en el enlace a la Mini App, en cuyo caso se abrirá a media altura de pantalla de forma predeterminada.

Ejemplos

https://t.me/botusername/appname
https://t.me/botusername/appname?startapp=command
https://t.me/botusername/appname?startapp=command&mode=compact

Bueno para:

Servicios web completos e integraciones que cualquier usuario puede abrir con un solo toque.
Servicios cooperativos, multijugador u orientados al trabajo en equipo dentro de un contexto de chat.
Los casos de uso son efectivos ilimitado.
Iniciar miniaplicaciones desde el menú adjunto
TL;DR: Los Mini App Bots pueden solicitar ser agregados directamente al menú de archivos adjuntos de un usuario, lo que permite iniciarlos rápidamente desde cualquier chat. Para probar este modo, abra esto enlace del menú adjunto para @DurgerKingBot, luego usa el Adjuntar menú en cualquier tipo de chat.

Los Mini App Bots pueden solicitar ser agregados directamente al menú de archivos adjuntos de un usuario, lo que permite iniciarlos rápidamente desde cualquier tipo de chat. Puedes configurar en qué tipos de chats se puede iniciar tu mini app desde el menú de archivos adjuntos (privados, grupos, supergrupos o canales).

La integración del menú adjunto actualmente solo está disponible para los principales anunciantes en el Plataforma de anuncios de Telegram. Sin embargo, Todos los bots Puedes usarlo en el probar el entorno del servidor.

Para habilitar esta función para su bot, abra @BotFather desde una cuenta en el servidor de prueba y envía el /setattach comando – o ir a Configuración del bot > Configurar menú de archivos adjuntos. Luego especifique la URL que se abrirá para iniciar la Mini Aplicación del bot a través de su ícono en el menú adjunto.

Puede agregar un elemento 'Configuración' al menú contextual de su Mini aplicación usando @BotFather. Cuando los usuarios seleccionen esta opción del menú, su bot recibirá un settingsButtonClicked evento.

Además de los del usuario configuración del tema, el bot recibirá información básica del usuario (ID, name, username, language_code, photo), así como información pública sobre el compañero de chat (ID, name, username, photo) o la información del chat (ID, type, title, username, photo) y un identificador único para la sesión de vista web consulta_id, que permite enviar mensajes de cualquier tipo al chat en nombre del usuario que abrió el bot.

El bot puede llamar al método API del bot respuestaWebAppQuery, que envía un mensaje en línea del usuario a través del bot al chat donde se inició y cierra la Mini App.

Puede leer más sobre cómo agregar bots al menú adjunto aquí.

Inicializando mini aplicaciones
Para conectar tu Mini App al cliente de Telegram, coloca el script aplicación web Telegram.js en el <head> etiqueta antes de cualquier otro script, usando este código:

<script src="https://telegram.org/js/telegram-web-app.js?62"></script>
Una vez conectado el script, a window.Telegram.WebApp El objeto estará disponible con los siguientes campos:

Campo	Tipo	Descripción
datos de inicio	Cadena	Una cadena con datos sin procesar transferidos a la Mini Aplicación, conveniente para Validación de datos.
ADVERTENCIA: Validar datos desde este campo antes de usarlo en el servidor del bot.
initDataInseguro	Datos de entrada de la aplicación web	Un objeto con datos de entrada transferidos a la Mini Aplicación.
ADVERTENCIA: No se debe confiar en los datos de este campo. Sólo debes utilizar datos de datos de inicio en el servidor del bot y sólo después de que haya sido validado.
versión	Cadena	La versión de la API Bot disponible en la aplicación Telegram del usuario.
plataforma	Cadena	El nombre de la plataforma de la aplicación Telegram del usuario.
esquema de color	Cadena	La combinación de colores que se utiliza actualmente en la aplicación Telegram: “claro” o “oscuro”.
También disponible como variable CSS var(--tg-color-scheme).
temaParams	Parámetros temáticos	Un objeto que contiene la configuración del tema actual utilizado en la aplicación Telegram.
está activo NUEVO	Booleano	API de bots 8.0+ Verdadero, si la Mini App está activa actualmente. Falso, si la Mini App está minimizada.
se amplía	Booleano	Verdadero, si la Mini App se expande hasta la altura máxima disponible. Falso, si la Mini App ocupa parte de la pantalla y se puede expandir a toda la altura usando el expandir() método.
altura de la ventana gráfica	Flotante	La altura actual del área visible de la Mini App. También disponible en CSS como variable var(--tg-viewport-height).

La aplicación puede mostrar solo la parte superior de la Mini App, quedando su parte inferior fuera del área de la pantalla. Desde esta posición, el usuario puede “tirar” de la Mini App hasta su altura máxima, mientras que el bot puede hacer lo mismo llamando al expandir() método. A medida que cambie la posición de la Mini App, el valor de altura actual del área visible se actualizará en tiempo real.

Tenga en cuenta que la frecuencia de actualización de este valor no es suficiente para seguir suavemente el borde inferior de la ventana. No debe utilizarse para fijar elementos de interfaz a la parte inferior del área visible. Es más apropiado utilizar el valor del viewportStableHeight campo para este propósito.
viewportAltura estable	Flotante	La altura del área visible de la Mini App en su último estado estable. También disponible en CSS como variable var(--tg-viewport-stable-height).

La aplicación puede mostrar solo la parte superior de la Mini App, quedando su parte inferior fuera del área de la pantalla. Desde esta posición, el usuario puede “tirar” de la Mini App hasta su altura máxima, mientras que el bot puede hacer lo mismo llamando al expandir() método. A diferencia del valor de viewportHeight, el valor de viewportStableHeight no cambia ya que la posición de la Mini Aplicación cambia con los gestos del usuario o durante las animaciones. El valor de viewportStableHeight se actualizará una vez completados todos los gestos y animaciones y la Mini App alcance su tamaño final.

Tenga en cuenta el evento viewportChanged con el parámetro pasado isStateStable=true, lo que le permitirá rastrear cuándo cambia el estado estable de la altura del área visible.
color del encabezado	Cadena	Color de encabezado actual en el #RRGGBB formato.
color de fondo	Cadena	Color de fondo actual en el #RRGGBB formato.
color de la barra inferior	Cadena	Color actual de la barra inferior en el #RRGGBB formato.
isClosingConfirmationHabilitado	Booleano	Verdadero, si el cuadro de diálogo de confirmación está habilitado mientras el usuario intenta cerrar la Mini Aplicación. Falso, si el cuadro de diálogo de confirmación está deshabilitado.
isVerticalSwipes habilitado	Booleano	Verdadero, si los deslizamientos verticales para cerrar o minimizar la Mini Aplicación están habilitados. Falso, si los deslizamientos verticales para cerrar o minimizar la Mini Aplicación están deshabilitados. En cualquier caso, el usuario aún podrá minimizar y cerrar la Mini App deslizando el encabezado de la Mini App.
es Pantalla completa NUEVO	Booleano	Verdadero, si la Mini Aplicación se muestra actualmente en modo de pantalla completa.
isOrientationLocked NUEVO	Booleano	Verdadero, si la orientación de la Mini App está bloqueada actualmente. Falso, si la orientación cambia libremente según la rotación del dispositivo.
Inserto de área segura NUEVO	Entrada de área segura	Se inserta un objeto que representa el área segura del dispositivo, teniendo en cuenta elementos de la interfaz de usuario del sistema, como muescas o barras de navegación.
contenidoSafeAreaInset NUEVO	Entrada de área segura de contenido	Un objeto que representa el área segura para mostrar contenido dentro de la aplicación, libre de elementos superpuestos de la interfaz de usuario de Telegram.
Botón de retroceso	Botón de retroceso	Un objeto para controlar el botón Atrás que se puede mostrar en el encabezado de la Mini Aplicación en la interfaz de Telegram.
Botón principal	Botón inferior	Un objeto para controlar el botón principal, que se muestra en la parte inferior de la Mini Aplicación en la interfaz de Telegram.
Botón secundario	Botón inferior	Un objeto para controlar el botón secundario, que se muestra en la parte inferior de la Mini App en la interfaz de Telegram.
Botón de configuración	Botón de configuración	Un objeto para controlar el elemento Configuración en el menú contextual de la Mini Aplicación en la interfaz de Telegram.
Comentarios hápticos	Comentarios hápticos	Un objeto para controlar la retroalimentación háptica.
Almacenamiento en la nube	Almacenamiento en la nube	Un objeto para controlar el almacenamiento en la nube.
Gerente Biométrico	Gerente Biométrico	Un objeto para controlar la biometría en el dispositivo.
Acelerómetro NUEVO	Acelerómetro	Un objeto para acceder a los datos del acelerómetro en el dispositivo.
Orientación del dispositivo NUEVO	Orientación del dispositivo	Un objeto para acceder a datos de orientación del dispositivo en el dispositivo.
Giroscopio NUEVO	Giroscopio	Un objeto para acceder a los datos del giroscopio en el dispositivo.
Administrador de ubicación NUEVO	Administrador de ubicación	Un objeto para controlar la ubicación en el dispositivo.
Almacenamiento de dispositivos NUEVO	Almacenamiento de dispositivos	Un objeto para almacenar y recuperar datos del almacenamiento local del dispositivo.
Almacenamiento seguro NUEVO	Almacenamiento seguro	Un objeto para almacenar y recuperar datos del almacenamiento seguro del dispositivo.
isVersionAtLeast(versión)	Función	Devuelve verdadero si la aplicación del usuario admite una versión de Bot API que sea igual o superior a la versión pasada como parámetro.
setHeaderColor(color)	Función	API de bots 6.1+ Un método que establece el color del encabezado de la aplicación en #RRGGBB formato. También puedes utilizar palabras clave bg_color y secundario_bg_color.

Hasta API de bots 6.9 Sólo puedes pasar Telegram.WebApp.themeParams.bg_color o Telegram.WebApp.themeParams.secundary_bg_color como un color o bg_color, secundario_bg_color palabras clave.
setBackgroundColor(color)	Función	API de bots 6.1+ Un método que establece el color de fondo de la aplicación en el #RRGGBB formato. También puedes utilizar palabras clave bg_color y secundario_bg_color.
setBottomBarColor(color)	Función	API de bots 7.10+ Un método que establece el color de la barra inferior de la aplicación en #RRGGBB formato. También puedes utilizar las palabras clave bg_color, secundario_bg_color, y barra_inferior_bg_color. Este color también se aplica a la barra de navegación en Android.
habilitarConfirmaciónDeCierre()	Función	API de bots 6.2+Un método que habilita un cuadro de diálogo de confirmación mientras el usuario intenta cerrar la Mini Aplicación.
deshabilitarConfirmación de cierre()	Función	API de bots 6.2+Un método que desactiva el cuadro de diálogo de confirmación mientras el usuario intenta cerrar la Mini Aplicación.
habilitarVerticalSwipes()	Función	API de bots 7.7+Un método que permite realizar deslizamientos verticales para cerrar o minimizar la aplicación Mini. Para comodidad del usuario, se recomienda habilitar siempre los deslizamientos a menos que entren en conflicto con los gestos de la aplicación Mini.
deshabilitarVerticalSwipes()	Función	API de bots 7.7+Un método que desactiva los deslizamientos verticales para cerrar o minimizar la aplicación Mini. Este método es útil si su aplicación Mini utiliza gestos de deslizamiento que pueden entrar en conflicto con los gestos para minimizar y cerrar la aplicación.
solicitudPantalla completa() NUEVO	Función	API de bots 8.0+ Un método que solicita abrir la Mini App en modo de pantalla completa. Aunque el encabezado es transparente en modo de pantalla completa, se recomienda que la Mini Aplicación configure el color del encabezado usando establecer color de encabezado método. Este color ayuda a determinar un color contrastante para la barra de estado y otros controles de la interfaz de usuario.
salirPantalla completa() NUEVO	Función	API de bots 8.0+Un método que solicita salir del modo de pantalla completa.
lockOrientation() NUEVO	Función	API de bots 8.0+Un método que bloquea la orientación de la Mini Aplicación a su modo actual (ya sea vertical u horizontal). Una vez bloqueada, la orientación permanece fija, independientemente de la rotación del dispositivo. Esto es útil si se necesita una orientación estable durante interacciones específicas.
desbloquearOrientación() NUEVO	Función	API de bots 8.0+Un método que desbloquea la orientación de la Mini App, permitiéndole seguir libremente la rotación del dispositivo. Utilice esto para restaurar los ajustes automáticos de orientación según la orientación del dispositivo.
addToHomeScreen() NUEVO	Función	API de bots 8.0+ Un método que solicita al usuario que agregue la Mini Aplicación a la pantalla de inicio. Después de agregar exitosamente el ícono, el homeScreenAdded El evento se activará si el dispositivo lo admite. Tenga en cuenta que si el dispositivo no puede determinar el estado de instalación, es posible que el evento no se reciba incluso si se ha agregado el ícono.
checkHomeScreenStatus([devolución de llamada]) NUEVO	Función	API de bots 8.0+ Un método que verifica si se admite agregar a la pantalla de inicio y si la Mini Aplicación ya se agregó. Si es opcional devolución se proporciona el parámetro, el devolución La función se llamará con un solo argumento estatus, que es una cadena que indica el estado de la pantalla de inicio. Valores posibles para estatus son:
- unsupported – la función no es compatible y no es posible agregar el ícono a la pantalla de inicio
- desconocido – la función es compatible y se puede agregar el ícono, pero no es posible determinar si el ícono ya se agregó
- añadido – el icono ya se ha añadido a la pantalla de inicio,
- miss – el icono no se ha agregado a la pantalla de inicio.
onEvent(tipo de evento, controlador de eventos)	Función	Un método que establece el controlador de eventos de la aplicación. Check la lista de eventos disponibles.
offEvent(tipo de evento, controlador de eventos)	Función	Un método que elimina un controlador de eventos previamente establecido.
sendData(datos)	Función	Un método utilizado para enviar datos al bot. Cuando se llama a este método, se envía un mensaje de servicio al bot que contiene los datos datos de una longitud de hasta 4096 bytes y la Mini App está cerrada. Ver el campo datos_aplicación_web en la clase Mensaje.

Este método solo está disponible para Mini Apps lanzadas a través de a Botón del teclado.
switchInlineQuery(consulta[, elegir_tipos_chat])	Función	API de bots 6.7+ Un método que inserta el nombre de usuario del bot y la línea especificada consulta en el campo de entrada del chat actual. La consulta puede estar vacía, en cuyo caso solo se insertará el nombre de usuario del bot. Si es opcional elegir_tipos_chat Se pasó el parámetro, el cliente solicita al usuario que elija un chat específico, luego abre ese chat e inserta el nombre de usuario del bot y la consulta en línea especificada en el campo de entrada. Puede especificar entre qué tipos de chats podrá elegir el usuario. Puede ser uno o más de los siguientes tipos: usuarios, bots, grupos, canales.
openLink(url[, opciones])	Función	Un método que abre un enlace en un navegador externo. La mini aplicación lo hará no estar cerrado.
API de bots 6.4+ Si el opcional opciones El parámetro se pasa con el campo try_instant_view=true, el enlace se abrirá en Vista instantánea modo si es posible.

Tenga en cuenta que este método solo se puede llamar en respuesta a la interacción del usuario con la interfaz de la Mini Aplicación (por ejemplo, un clic dentro de la Mini Aplicación o en el botón principal)
openTelegramLink(url)	Función	Un método que abre un enlace de Telegram dentro de la aplicación de Telegram. La miniprogramación lo hará no se cerrará después de llamar a este método.

Hasta API de bots 7.0 La mini aplicación will se cerrará después de llamar a este método.
openInvoice(url[, devolución de llamada])	Función	API de bots 6.1+ Un método que abre una factura utilizando el enlace url. La Mini App recibirá el evento facturaCerrada cuando la factura esté cerrada. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función y se pasará el estado de la factura como primer argumento.
shareToStory(media_url[, parámetros])	Función	API de bots 7.8+ Un método que abre el editor de historias nativo con los medios especificados en el media_url parámetro como URL HTTPS. Una opción params argumento del tipo Params para compartir historias describe configuraciones adicionales para compartir.
shareMessage(msg_id[, devolución de llamada]) NUEVO	Función	API de bots 8.0+ Un método que abre un cuadro de diálogo que permite al usuario compartir un mensaje proporcionado por el bot. Si es opcional devolución se proporciona el parámetro, el devolución La función se llamará con un booleano como primer argumento, indicando si el mensaje se envió correctamente. El ID del mensaje pasado a este método debe pertenecer a un Mensaje preparado en línea obtenido previamente mediante el método Bot API guardarMensajePreparadoEnLínea.
setEmojiStatus(custom_emoji_id[, parámetros, devolución de llamada])	Función	API de bots 8.0+ Un método que abre un cuadro de diálogo que permite al usuario establecer el emoji personalizado especificado como su estado. Una opción params argumento de tipo Parámetros de estado de emojis especifica configuraciones adicionales, como la duración. Si es opcional devolución se proporciona el parámetro, el devolución La función se llamará con un booleano como primer argumento, indicando si se estableció el estado.

Nota: este método abre un cuadro de diálogo nativo y no se puede utilizar para establecer el estado del emoji sin la interacción manual del usuario. Para cambios totalmente programáticos, debe utilizar el método Bot API setUserEmojiStatus después de obtener autorización para hacerlo a través del método de la Mini Aplicación requestEmojiStatusAccess.
requestEmojiStatusAccess([devolución de llamada]) NUEVO	Función	API de bots 8.0+ Un método que muestra una ventana emergente nativa solicitando permiso para que el bot administre el estado del emoji del usuario. Si es opcional devolución Se pasó el parámetro, el devolución La función se llamará cuando se cierre la ventana emergente y el primer argumento será un valor booleano que indica si el usuario otorgó este acceso.
downloadFile(parámetros[, devolución de llamada]) NUEVO	Función	API de bots 8.0+ Un método que muestra una ventana emergente nativa que solicita al usuario que descargue un archivo especificado por el params argumento de tipo DescargarFileParams. Si es opcional devolución se proporciona el parámetro, el devolución La función se llamará cuando se cierre la ventana emergente, y el primer argumento será un valor booleano que indica si el usuario aceptó la solicitud de descarga.
ocultarTeclado() NUEVO	Función	API de bots 9.1+Un método que oculta el teclado en pantalla, si está visible actualmente. No hace nada si el teclado no está activo.
showPopup(parámetros[, devolución de llamada])	Función	API de bots 6.2+ Un método que muestra una ventana emergente nativa descrita por el params argumento del tipo Parámetros emergentes. La Mini App recibirá el evento popupCerrado cuando la ventana emergente está cerrada. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función y al campo id del botón presionado se pasará como primer argumento.
showAlert(mensaje[, devolución de llamada])	Función	API de bots 6.2+ Un método que muestra mensaje en una alerta simple con un botón 'Cerrar'. Si es opcional devolución Se pasó el parámetro, el devolución La función se llamará cuando se cierre la ventana emergente.
showConfirm(mensaje[, devolución de llamada])	Función	API de bots 6.2+ Un método que muestra mensaje en una ventana de confirmación simple con los botones 'Aceptar' y 'Cancelar'. Si es opcional devolución Se pasó el parámetro, el devolución La función se llamará cuando se cierre la ventana emergente y el primer argumento será un valor booleano que indica si el usuario presionó el botón "Aceptar".
showScanQrPopup(parámetros[, devolución de llamada])	Función	API de bots 6.4+ Un método que muestra una ventana emergente nativa para escanear un código QR descrito por el params argumento del tipo Parámetros popup de ScanQr. La Mini App recibirá el evento qrTextoRecibido cada vez que el escáner detecta un código con datos de texto. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función y se pasará el texto del código QR como primer argumento. Regresando verdadero Dentro de esta función de devolución de llamada se cierra la ventana emergente. Empezando desde API de bots 7.7, la Mini App recibirá el scanQrPopupCerrado evento si el usuario cierra la ventana emergente nativa para escanear un código QR.
cerrarScanQrPopup()	Función	API de bots 6.4+ Un método que cierra la ventana emergente nativa para escanear un código QR abierto con el mostrarScanQrPopup método. Ejecútelo si recibió datos válidos en el evento qrTextoRecibido.
readTextFromClipboard([devolución de llamada])	Función	API de bots 6.4+ Un método que solicita texto del portapapeles. La Mini App recibirá el evento texto del portapapeles recibido. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función y el texto del portapapeles se pasará como primer argumento.

Nota: este método solo se puede llamar para Mini Apps iniciadas desde el menú adjunto y solo en respuesta a una interacción del usuario con la interfaz de Mini App (por ejemplo, un clic dentro de Mini App o en el botón principal).
requestWriteAccess([devolución de llamada])	Función	API de bots 6.9+ Un método que muestra una ventana emergente nativa solicitando permiso para que el bot envíe mensajes al usuario. Si es opcional devolución Se pasó el parámetro, el devolución La función se llamará cuando se cierre la ventana emergente y el primer argumento será un valor booleano que indica si el usuario otorgó este acceso.
requestContact([devolución de llamada])	Función	API de bots 6.9+ Un método que muestra una ventana emergente nativa que solicita al usuario su número de teléfono. Si es opcional devolución Se pasó el parámetro, el devolución La función se llamará cuando se cierre la ventana emergente y el primer argumento será un valor booleano que indica si el usuario compartió su número de teléfono.
requestChat(req_id[, devolución de llamada]) NUEVO	Función	API de bots 9.6+ Un método que abre un cuadro de diálogo que permite al usuario seleccionar un chat existente o crear uno nuevo. Si es opcional devolución se proporciona el parámetro, el devolución La función se llamará con un booleano como primer argumento, indicando si el mensaje se envió correctamente. El ID de solicitud pasado a este método debe pertenecer a un Botón de teclado preparado obtenido previamente mediante el método Bot API Botón de teclado preparado para guardar.
listo()	Función	Un método que informa a la aplicación Telegram que la Mini Aplicación está lista para mostrarse.
Se recomienda llamar a este método lo antes posible, tan pronto como se carguen todos los elementos esenciales de la interfaz. Una vez llamado este método, se oculta el marcador de carga y se muestra la Mini App.
Si no se llama al método, el marcador de posición se ocultará solo cuando la página esté completamente cargada.
expandir()	Función	Un método que expande la Mini App a la altura máxima disponible. Para saber si la Mini App está expandida a la altura máxima, consulte el valor de la Telegram.WebApp.isExpanded parámetro
cerrar()	Función	Un método que cierra la Mini App.
Parámetros temáticos
Las mini aplicaciones pueden hacerlo ajustar la apariencia de la interfaz para que coincida con la aplicación del usuario de Telegram en tiempo real. Este objeto contiene la configuración actual del tema del usuario:

Campo	Tipo	Descripción
bg_color	Cadena	Opcional. Color de fondo en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-bg-color).
color_texto	Cadena	Opcional. Color del texto principal en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-text-color).
hint_color	Cadena	Opcional. Sugerencia de color de texto en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-hint-color).
link_color	Cadena	Opcional. Color del enlace en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-link-color).
botón_color	Cadena	Opcional. Color del botón en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-button-color).
botón_texto_color	Cadena	Opcional. Color del texto del botón en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-button-text-color).
secundario_bg_color	Cadena	Opcional. API de bots 6.1+ Color de fondo secundario en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-secondary-bg-color).
encabezado_bg_color	Cadena	Opcional. API de bots 7.0+ Color de fondo del encabezado en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-header-bg-color).
color_barra_bg_inferior	Cadena	Opcional. API de bots 7.10+ Color de fondo inferior en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-bottom-bar-bg-color).
acento_texto_color	Cadena	Opcional. API de bots 7.0+ Color del texto acentuado en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-accent-text-color).
sección_bg_color	Cadena	Opcional. API de bots 7.0+ Color de fondo para la sección en el #RRGGBB formato. Se recomienda utilizar esto junto con secundario_bg_color.
También disponible como variable CSS var(--tg-theme-section-bg-color).
sección_encabezado_texto_color	Cadena	Opcional. API de bots 7.0+ Color del texto del encabezado de la sección en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-section-header-text-color).
sección_separador_color	Cadena	Opcional. API de bots 7.6+ Color del separador de secciones en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-section-separator-color).
subtítulo_texto_color	Cadena	Opcional. API de bots 7.0+ Color del texto del subtítulo en el #RRGGBB formato.
También disponible como variable CSS var(--tg-theme-subtitle-text-color).
destructive_text_color	String	Optional. Bot API 7.0+ Text color for destructive actions in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-destructive-text-color).
Explicación de WebViewColors
StoryShareParams
This object describes additional sharing settings for the native story editor.

Field	Type	Description
text	String	Optional. The caption to be added to the media, 0-200 characters for regular users and 0-2048 characters for premium subscribers.
widget_link	StoryWidgetLink	Optional. An object that describes a widget link to be included in the story. Note that only premium subscribers can post stories with links.
StoryWidgetLink
This object describes a widget link to be included in the story.

Field	Type	Description
url	String	The URL to be included in the story.
name	String	Opcional. El nombre que se mostrará para el enlace del widget, 0-48 caracteres.
Parámetros popup de ScanQr
Este objeto describe la ventana emergente nativa para escanear códigos QR.

Campo	Tipo	Descripción
texto	Cadena	Opcional. El texto que se mostrará bajo el encabezado 'Escanear QR', de 0 a 64 caracteres.
Parámetros emergentes
Este objeto describe la ventana emergente nativa.

Campo	Tipo	Descripción
título	Cadena	Opcional. El texto que se mostrará en el título emergente, de 0 a 64 caracteres.
mensaje	Cadena	El mensaje que se mostrará en el cuerpo de la ventana emergente, 1-256 caracteres.
botones	Matriz de Botón emergente	Opcional. Lista de botones que se mostrarán en la ventana emergente, 1-3 botones. Establecer en [{“tipo”:“cerrar”}] por defecto.
Botón emergente
Este objeto describe el botón emergente nativo.

Campo	Tipo	Descripción
id	Cadena	Opcional. Identificador del botón, 0-64 caracteres. Establecido en cadena vacía de forma predeterminada.
Si se presiona el botón, es id se devuelve en la devolución de llamada y el popupCerrado evento.
tipo	Cadena	Opcional. Tipo de botón. Establecer en predeterminado por defecto.
Puede ser uno de estos valores:
- predeterminado, un botón con el estilo predeterminado,
- ok, un botón con el texto localizado “OK”,
- cerrar, un botón con el texto localizado “Cerrar”,
- cancelar, un botón con el texto localizado “Cancelar”,
- destructivo, un botón con un estilo que indica una acción destructiva (por ejemplo “Eliminar”, “Eliminar”, etc.).
texto	Cadena	Opcional. El texto que se mostrará en el botón, 0-64 caracteres. Requerido si tipo es predeterminado o destructivo. Irrelevante para otros tipos.
Parámetros de estado de emojis
Este objeto describe configuraciones adicionales para establecer el estado de un emoji.

Campo	Tipo	Descripción
duración	Entero	Opcional. La duración durante la cual permanecerá establecido el estado, en segundos.
DescargarFileParams
Este objeto describe los parámetros para la solicitud de descarga de archivos.

Nota: Para garantizar un comportamiento consistente de descarga de archivos en todas las plataformas, incluya los encabezados HTTP Content-Disposition: attachment; filename="<file_name>" y Access-Control-Allow-Origin: https://web.telegram.org en la respuesta del servidor. Sin estos encabezados, es posible que la descarga no funcione como se esperaba, especialmente en plataformas web.

Campo	Tipo	Descripción
url	Cadena	La URL HTTPS del archivo a descargar.
nombre_archivo	Cadena	El nombre sugerido para el archivo descargado.
Entrada de área segura
Este objeto representa los insertos de área segura definidos por el sistema, proporcionando valores de relleno para garantizar que el contenido permanezca dentro de los límites visibles, evitando la superposición con elementos de la interfaz de usuario del sistema, como muescas o barras de navegación.

Campo	Tipo	Descripción
top	Entero	La parte superior está insertada en píxeles, lo que representa el espacio a evitar en la parte superior de la pantalla. También disponible como variable CSS var(--tg-safe-area-inset-top).
fondo	Entero	La parte inferior está insertada en píxeles, lo que representa el espacio a evitar en la parte inferior de la pantalla. También disponible como variable CSS var(--tg-safe-area-inset-bottom).
izquierda	Entero	El recuadro izquierdo en píxeles, que representa el espacio a evitar en el lado izquierdo de la pantalla. También disponible como variable CSS var(--tg-safe-area-inset-left).
bien	Entero	El recuadro derecho en píxeles, que representa el espacio a evitar en el lado derecho de la pantalla. También disponible como variable CSS var(--tg-safe-area-inset-right).
Explicación de SafeAreaInset
Entrada de área segura de contenido
Este objeto representa los insertos de área segura definidos por el contenido, proporcionando valores de relleno para garantizar que el contenido permanezca dentro de los límites visibles, evitando la superposición con los elementos de la interfaz de usuario de Telegram.

Campo	Tipo	Descripción
top	Entero	La parte superior está insertada en píxeles, lo que representa el espacio a evitar en la parte superior del área de contenido. También disponible como variable CSS var(--tg-content-safe-area-inset-top).
fondo	Entero	La parte inferior está insertada en píxeles, lo que representa el espacio a evitar en la parte inferior del área de contenido. También disponible como variable CSS var(--tg-content-safe-area-inset-bottom).
izquierda	Entero	El recuadro izquierdo en píxeles, que representa el espacio a evitar en el lado izquierdo del área de contenido. También disponible como variable CSS var(--tg-content-safe-area-inset-left).
bien	Entero	El recuadro derecho en píxeles, que representa el espacio a evitar en el lado derecho del área de contenido. También disponible como variable CSS var(--tg-content-safe-area-inset-right).
Explicación de ContentSafeAreaInset
BackButton
This object controls the back button, which can be displayed in the header of the Mini App in the Telegram interface.

Field	Type	Description
isVisible	Boolean	Shows whether the button is visible. Set to false by default.
onClick(callback)	Function	Bot API 6.1+ A method that sets the button press event handler. An alias for Telegram.WebApp.onEvent('backButtonClicked', callback)
offClick(callback)	Function	Bot API 6.1+ A method that removes the button press event handler. An alias for Telegram.WebApp.offEvent('backButtonClicked', callback)
show()	Function	Bot API 6.1+ A method to make the button active and visible.
hide()	Function	Bot API 6.1+ A method to hide the button.
All these methods return the BackButton object so they can be chained.

BottomButton
This object controls the button that is displayed at the bottom of the Mini App in the Telegram interface.

Field	Type	Description
type	String	Sólo lectura. Tipo de botón. Puede ser cualquiera de los dos principal para el botón principal o secundaria para el botón secundario.
iconCustomEmojiId	Cadena	API de bots 9.5+Identificador único del emoji personalizado que se muestra antes del texto del botón.
texto	Cadena	Texto del botón actual. Establecer en Continuar para el botón principal y Cancelar para el botón secundario por defecto.
color	Cadena	Color actual del botón. Establecer en themeParams.button_color para el botón principal y themeParams.bottom_bar_bg_color para el botón secundario por defecto.
color del texto	Cadena	Color actual del texto del botón. Establecer en themeParams.button_text_color para el botón principal y themeParams.button_color para el botón secundario por defecto.
es visible	Booleano	Muestra si el botón está visible. Establecer en falso por defecto.
está activo	Booleano	Muestra si el botón está activo. Establecer en verdadero por defecto.
tiene efecto de brillo	Booleano	API de bots 7.10+ Muestra si el botón tiene efecto de brillo. Establecer en falso por defecto.
posición	Cadena	API de bots 7.10+ Posición del botón secundario. No definido para el botón principal. Se aplica sólo si los botones principal y secundario están visibles. Establecer en izquierda por defecto.
Valores admitidos:
- izquierda, se muestra a la izquierda del botón principal,
- bien, se muestra a la derecha del botón principal,
- top, se muestra encima del botón principal,
- fondo, se muestra debajo del botón principal.
esProgresoVisible	Booleano	Sólo lectura. Muestra si el botón muestra un indicador de carga.
setText(texto)	Función	Un método para configurar el texto del botón.
onClick(devolución de llamada)	Función	Un método que establece el controlador de eventos de pulsación del botón. Un alias para Telegram.WebApp.onEvent('mainButtonClicked', callback)
offClick(devolución de llamada)	Función	A method that removes the button's press event handler. An alias for Telegram.WebApp.offEvent('mainButtonClicked', callback)
show()	Function	A method to make the button visible.
Note that opening the Mini App from the attachment menu hides the main button until the user interacts with the Mini App interface.
hide()	Function	A method to hide the button.
enable()	Function	A method to enable the button.
disable()	Function	A method to disable the button.
showProgress(leaveActive)	Function	A method to show a loading indicator on the button.
It is recommended to display loading progress if the action tied to the button may take a long time. By default, the button is disabled while the action is in progress. If the parameter leaveActive=true is passed, the button remains enabled.
hideProgress()	Function	A method to hide the loading indicator.
setParams(params)	Function	Un método para configurar los parámetros del botón. El params El parámetro es un objeto que contiene uno o varios campos que deben cambiarse:
icon_custom_emoji_id - API de bots 9.5+ id del emoji del icono del botón;
texto - texto del botón;
color - color del botón;
color_texto - color del texto del botón;
tiene_efecto_brillo - API de bots 7.10+ habilitar el efecto de brillo;
posición - posición del botón secundario;
es_activo - habilitar el botón;
es_visible - mostrar el botón.
Todos estos métodos devuelven el objeto BottomButton para que puedan encadenarse.

Botón de configuración
This object controls the Settings item in the context menu of the Mini App in the Telegram interface.

Field	Type	Description
isVisible	Boolean	Shows whether the context menu item is visible. Set to false by default.
onClick(callback)	Function	Bot API 7.0+ A method that sets the press event handler for the Settings item in the context menu. An alias for Telegram.WebApp.onEvent('settingsButtonClicked', callback)
offClick(callback)	Function	Bot API 7.0+ A method that removes the press event handler from the Settings item in the context menu. An alias for Telegram.WebApp.offEvent('settingsButtonClicked', callback)
show()	Function	Bot API 7.0+ A method to make the Settings item in the context menu visible.
hide()	Function	Bot API 7.0+ A method to hide the Settings item in the context menu.
All these methods return the SettingsButton object so they can be chained.

HapticFeedback
This object controls haptic feedback.

Field	Type	Description
impactOccurred(style)	Function	Bot API 6.1+ Un método indica que se produjo un impacto. La aplicación Telegram puede reproducir las hápticas apropiadas según el valor de estilo pasado. El estilo puede ser uno de estos valores:
- luz, indica una colisión entre objetos de interfaz de usuario pequeños o livianos,
- medio, indica una colisión entre objetos de interfaz de usuario de tamaño mediano o mediano,
- pesado, indica una colisión entre objetos de interfaz de usuario grandes o pesados
- rígido, indica una colisión entre objetos de interfaz de usuario duros o inflexibles,
- suave, indica una colisión entre objetos de interfaz de usuario blandos o flexibles.
notificaciónOcurrida(tipo)	Función	API de bots 6.1+ Un método indica que una tarea o acción ha tenido éxito, ha fallado o ha producido una advertencia. La aplicación Telegram puede reproducir las hápticas apropiadas según el valor de tipo pasado. El tipo puede ser uno de estos valores:
- error, indica que una tarea o acción ha fallado,
- éxito, indica que una tarea o acción se ha completado con éxito,
- advertencia, indica que una tarea o acción produjo una advertencia.
selecciónCambiada()	Función	API de bots 6.1+ Un método indica que el usuario ha cambiado una selección. La aplicación Telegram puede reproducir las hápticas apropiadas.

No utilice estos comentarios cuando el usuario realice o confirme una selección; utilícelos sólo cuando la selección cambie.
Todos estos métodos devuelven el objeto HapticFeedback para que puedan encadenarse.

Almacenamiento en la nube
Este objeto controla el almacenamiento en la nube. Cada bot puede almacenar hasta 1024 elementos por usuario en el almacenamiento en la nube.

Campo	Tipo	Descripción
setItem(clave, valor[, devolución de llamada])	Función	API de bots 6.9+ Un método que almacena un valor en el almacenamiento en la nube utilizando la clave especificada. La clave debe contener únicamente entre 1 y 128 caracteres A-Z, a-z, 0-9, _ y - están permitidos. El valor debe contener entre 0 y 4096 caracteres. Puede almacenar hasta 1024 claves en el almacenamiento en la nube. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si el valor fue almacenado.
getItem(clave, devolución de llamada)	Función	API de bots 6.9+ Un método que recibe un valor del almacenamiento en la nube utilizando la clave especificada. La clave debe contener únicamente entre 1 y 128 caracteres A-Z, a-z, 0-9, _ y - están permitidos. En caso de error, el devolución Se llamará a la función y el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el valor se pasará como segundo argumento.
getItems(claves, devolución de llamada)	Función	API de bots 6.9+ Un método que recibe valores del almacenamiento en la nube utilizando las claves especificadas. Las claves deben contener únicamente entre 1 y 128 caracteres A-Z, a-z, 0-9, _ y - están permitidos. En caso de error, el devolución Se llamará a la función y el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y los valores se pasarán como segundo argumento.
removeItem(clave[, devolución de llamada])	Función	API de bots 6.9+ Un método que elimina un valor del almacenamiento en la nube utilizando la clave especificada. La clave debe contener únicamente entre 1 y 128 caracteres A-Z, a-z, 0-9, _ y - están permitidos. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si se eliminó el valor.
removeItems(claves[, devolución de llamada])	Función	API de bots 6.9+ Un método que elimina valores del almacenamiento en la nube utilizando las claves especificadas. Las claves deben contener únicamente entre 1 y 128 caracteres A-Z, a-z, 0-9, _ y - están permitidos. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si se eliminaron los valores.
getKeys(devolución de llamada)	Función	API de bots 6.9+ Un método que recibe la lista de todas las claves almacenadas en el almacenamiento en la nube. En caso de error, el devolución Se llamará a la función y el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y la lista de claves se pasará como segundo argumento.
Todos estos métodos devuelven el Almacenamiento en la nube objeto, para que puedan encadenarse.

Gerente Biométrico
Este objeto controla la biometría en el dispositivo. Antes del primer uso de este objeto, es necesario inicializarlo utilizando el init método.

Campo	Tipo	Descripción
está iniciado	Booleano	Muestra si el objeto biométrico está inicializado.
Está disponible en biometría	Booleano	Muestra si la biometría está disponible en el dispositivo actual.
tipo biométrico	Cadena	The type of biometrics currently available on the device. Can be one of these values:
- finger, fingerprint-based biometrics,
- face, face-based biometrics,
- unknown, biometrics of an unknown type.
isAccessRequested	Boolean	Shows whether permission to use biometrics has been requested.
isAccessGranted	Boolean	Shows whether permission to use biometrics has been granted.
isBiometricTokenSaved	Boolean	Shows whether the token is saved in secure storage on the device.
deviceId	String	A unique device identifier that can be used to match the token to the device.
init([callback])	Function	Bot API 7.2+ Un método que inicializa el objeto BiometricManager. Debe llamarse antes del primer uso del objeto. Si es opcional devolución Se pasó el parámetro, el devolución La función se llamará cuando se inicialice el objeto.
requestAccess(parámetros[, devolución de llamada])	Función	API de bots 7.2+ Un método que solicita permiso para utilizar datos biométricos de acuerdo con la params argumento de tipo Parámetros de acceso a solicitudes biométricas. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función y el primer argumento será un valor booleano que indica si el usuario otorgó acceso.
autenticar(parámetros[, devolución de llamada])	Función	API de bots 7.2+ Un método que autentica al usuario mediante biometría de acuerdo con la params argumento de tipo Parámetros de autenticación biométricos. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función y el primer argumento será un valor booleano que indica si el usuario se autenticó correctamente. Si es así, el segundo argumento será un token biométrico.
updateBiometricToken(token, [devolución de llamada])	Función	API de bots 7.2+ Un método que actualiza el token biométrico en un almacenamiento seguro en el dispositivo. Para eliminar el token, pase una cadena vacía. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función y el primer argumento será un valor booleano que indica si el token se actualizó.
openSettings()	Function	Bot API 7.2+ A method that opens the biometric access settings for bots. Useful when you need to request biometrics access to users who haven't granted it yet.

Note that this method can be called only in response to user interaction with the Mini App interface (e.g. a click inside the Mini App or on the main button)
All these methods return the BiometricManager object so they can be chained.

BiometricRequestAccessParams
This object describes the native popup for requesting permission to use biometrics.

Field	Type	Description
reason	String	Optional. The text to be displayed to a user in the popup describing why the bot needs access to biometrics, 0-128 characters.
BiometricAuthenticateParams
This object describes the native popup for authenticating the user using biometrics.

Field	Type	Description
reason	String	Optional. The text to be displayed to a user in the popup describing why you are asking them to authenticate and what action you will be taking based on that authentication, 0-128 characters.
Accelerometer
This object provides access to accelerometer data on the device.

Field	Type	Description
isStarted	Boolean	Indicates whether accelerometer tracking is currently active.
x	Float	The current acceleration in the X-axis, measured in m/s².
y	Float	The current acceleration in the Y-axis, measured in m/s².
z	Float	The current acceleration in the Z-axis, measured in m/s².
start(params[, callback])	Function	Bot API 8.0+ Comienza a rastrear los datos del acelerómetro utilizando params de tipo Parámetros de inicio del acelerómetro. Si es opcional devolución Se proporciona el parámetro, el devolución Se llamará a la función con un valor booleano que indica si el seguimiento se inició correctamente.
detener([devolución de llamada])	Función	API de bots 8.0+ Detiene el seguimiento de los datos del acelerómetro. Si es opcional devolución Se proporciona el parámetro, el devolución Se llamará a la función con un valor booleano que indica si el seguimiento se detuvo correctamente.
Todos estos métodos devuelven el Acelerómetro objeto para que puedan encadenarse.

Acelerómetro
Parámetros de inicio del acelerómetro
Este objeto define los parámetros para iniciar el seguimiento del acelerómetro.

Campo	Tipo	Descripción
refrescar_tasa	Entero	Optional. The refresh rate in milliseconds, with acceptable values ranging from 20 to 1000. Set to 1000 by default. Note that refresh_rate may not be supported on all platforms, so the actual tracking frequency may differ from the specified value.
DeviceOrientation
This object provides access to orientation data on the device.

Field	Type	Description
isStarted	Boolean	Indicates whether device orientation tracking is currently active.
absolute	Boolean	A boolean that indicates whether or not the device is providing orientation data in absolute values.
alpha	Float	The rotation around the Z-axis, measured in radians.
beta	Float	The rotation around the X-axis, measured in radians.
gamma	Float	The rotation around the Y-axis, measured in radians.
start(params[, callback])	Function	Bot API 8.0+ Comienza a rastrear los datos de orientación del dispositivo mediante params de tipo Parámetros de inicio de orientación del dispositivo. Si es opcional devolución Se proporciona el parámetro, el devolución Se llamará a la función con un valor booleano que indica si el seguimiento se inició correctamente.
detener([devolución de llamada])	Función	API de bots 8.0+ Detiene el seguimiento de los datos de orientación del dispositivo. Si es opcional devolución Se proporciona el parámetro, el devolución Se llamará a la función con un valor booleano que indica si el seguimiento se detuvo correctamente.
Todos estos métodos devuelven el Orientación del dispositivo objeto para que puedan encadenarse.

Orientación del dispositivo
Parámetros de inicio de orientación del dispositivo
Este objeto define los parámetros para iniciar el seguimiento de la orientación del dispositivo.

Campo	Tipo	Descripción
refrescar_tasa	Entero	Opcional. La frecuencia de actualización en milisegundos, con valores aceptables que oscilan entre 20 y 1000. Establecer en 1000 por defecto. Tenga en cuenta que refrescar_tasa Es posible que no sea compatible con todas las plataformas, por lo que la frecuencia de seguimiento real puede diferir del valor especificado.
necesidad_absoluta	Booleano	Opcional. Pasar verdadero para recibir datos de orientación absoluta, lo que le permite determinar la actitud del dispositivo en relación con el norte magnético. Utilice esta opción si implementa funciones como una brújula en su aplicación. Si los datos relativos son suficientes, pase falso. Establecer en falso por defecto.

Nota: Tenga en cuenta que es posible que algunos dispositivos no admitan datos de orientación absoluta. En tales casos, recibirá datos relativos incluso si necesidad_absoluta=verdadero se aprueba. Comprueba el Orientación del dispositivo.absoluta parámetro para determinar si los datos proporcionados son absolutos o relativos.
Giroscopio
Este objeto proporciona acceso a los datos del giroscopio en el dispositivo.

Campo	Tipo	Descripción
isStarted	Booleano	Indicates whether gyroscope tracking is currently active.
x	Float	The current rotation rate around the X-axis, measured in rad/s.
y	Float	The current rotation rate around the Y-axis, measured in rad/s.
z	Float	The current rotation rate around the Z-axis, measured in rad/s.
start(params[, callback])	Function	Bot API 8.0+ Starts tracking gyroscope data using params of type GyroscopeStartParams. If an optional callback parameter is provided, the callback function will be called with a boolean indicating whether tracking was successfully started.
stop([callback])	Function	Bot API 8.0+ Detiene el seguimiento de los datos del giroscopio. Si es opcional devolución Se proporciona el parámetro, el devolución Se llamará a la función con un valor booleano que indica si el seguimiento se detuvo correctamente.
Todos estos métodos devuelven el Giroscopio objeto para que puedan encadenarse.

Giroscopio
Parámetros de inicio del giroscopio
Este objeto define los parámetros para iniciar el seguimiento del giroscopio.

Campo	Tipo	Descripción
refrescar_tasa	Entero	Opcional. La frecuencia de actualización en milisegundos, con valores aceptables que oscilan entre 20 y 1000. Establecer en 1000 por defecto. Tenga en cuenta que refrescar_tasa Es posible que no sea compatible con todas las plataformas, por lo que la frecuencia de seguimiento real puede diferir del valor especificado.
Administrador de ubicación
This object controls location access on the device. Before the first use of this object, it needs to be initialized using the init method.

Field	Type	Description
isInited	Boolean	Shows whether the LocationManager object has been initialized.
isLocationAvailable	Boolean	Shows whether location services are available on the current device.
isAccessRequested	Boolean	Shows whether permission to use location has been requested.
isAccessGranted	Boolean	Shows whether permission to use location has been granted.
init([callback])	Function	Bot API 8.0+ A method that initializes the LocationManager object. It should be called before the object's first use. If an optional callback parameter is provided, the callback function will be called when the object is initialized.
getLocation(callback)	Function	Bot API 8.0+ Un método que solicita datos de ubicación. El devolución La función se llamará con nulo como primer argumento si no se concedió acceso a la ubicación, o a un objeto de tipo Datos de ubicación como primer argumento si el acceso fue exitoso.
configuración abierta()	Función	API de bots 8.0+ Un método que abre la configuración de acceso a la ubicación de los bots. Útil cuando necesitas solicitar acceso a la ubicación a usuarios que aún no lo han concedido.

Tenga en cuenta que este método solo se puede llamar en respuesta a la interacción del usuario con la interfaz de la Mini Aplicación (por ejemplo, un clic dentro de la Mini Aplicación o en el botón principal).
Todos estos métodos devuelven el Administrador de ubicación objeto para que puedan encadenarse.

Datos de ubicación
Este objeto contiene datos sobre la ubicación actual.

Campo	Tipo	Descripción
latitud	Flotante	Latitud en grados.
longitud	Flotante	Longitud en grados.
altitud	Flotante	Altitud sobre el nivel del mar en metros. nulo si los datos de altitud no están disponibles en el dispositivo.
curso	Flotante	La dirección en la que se mueve el dispositivo en grados (0 = Norte, 90 = Este, 180 = Sur, 270 = Oeste). nulo si los datos del curso no están disponibles en el dispositivo.
velocidad	Flotante	La velocidad del dispositivo en m/s. nulo si los datos de velocidad no están disponibles en el dispositivo.
precisión_horizontal	Flotante	Precisión de los valores de latitud y longitud en metros. nulo si los datos de precisión horizontal no están disponibles en el dispositivo.
precisión_vertical	Flotante	Precisión del valor de altitud en metros. nulo si los datos de precisión vertical no están disponibles en el dispositivo.
curso_precisión	Flotante	Accuracy of the course value in degrees. null if course accuracy data is not available on the device.
speed_accuracy	Float	Accuracy of the speed value in m/s. null if speed accuracy data is not available on the device.
DeviceStorage
This object provides access to persistent local storage on the user’s device. It is conceptually similar to the browser's localStorage API, but integrated within the Telegram client. All data is stored locally and is available only to the bot that created it. Each bot can store up to 5 MB per user using this storage.

Field	Type	Description
setItem(key, value[, callback])	Function	Bot API 9.0+ Un método que almacena un valor en el almacenamiento local del dispositivo utilizando la clave especificada. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si el valor fue almacenado.
getItem(clave, devolución de llamada)	Función	API de bots 9.0+ Un método que recibe un valor del almacenamiento local del dispositivo utilizando la clave especificada. En caso de error, el devolución Se llamará a la función y el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el valor se pasará como segundo argumento.
removeItem(clave[, devolución de llamada])	Función	API de bots 9.0+ Un método que elimina un valor del almacenamiento local del dispositivo utilizando la clave especificada. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si se eliminó el valor.
clear([devolución de llamada])	Función	API de bots 9.0+ Un método que borra todas las claves previamente almacenadas por el bot en el almacenamiento local del dispositivo. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si se eliminaron todos los valores.
Todos estos métodos devuelven el Almacenamiento de dispositivos objeto, para que puedan encadenarse.

Almacenamiento seguro
Este objeto proporciona acceso a un almacenamiento seguro en el dispositivo del usuario para datos confidenciales. En iOS, utiliza el sistema Llavero; en Android, utiliza el Almacén de claves. Esto garantiza que todos los valores almacenados estén cifrados en reposo y sean inaccesibles para aplicaciones no autorizadas.

El almacenamiento seguro es adecuado para almacenar tokens, secretos, estado de autenticación y otra información confidencial específica del usuario. Cada bot puede almacenar hasta 10 artículos por usuario.

Campo	Tipo	Descripción
setItem(clave, valor[, devolución de llamada])	Función	API de bots 9.0+ Un método que almacena un valor en el almacenamiento seguro del dispositivo utilizando la clave especificada. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si el valor fue almacenado.
getItem(clave, devolución de llamada)	Función	API de bots 9.0+ Un método que recibe un valor del almacenamiento seguro del dispositivo utilizando la clave especificada. En caso de error, el devolución Se llamará a la función y el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el valor se pasará como segundo argumento. Si no se encontró la clave, el segundo argumento será nulo, y el tercer argumento será un valor booleano que indica si la clave se puede restaurar desde el dispositivo actual.
restoreItem(clave[, devolución de llamada])	Función	API de bots 9.0+ Intenta restaurar una clave que existía anteriormente en el dispositivo actual. Cuando se llame, se le pedirá permiso al usuario para restaurar el valor. Si el usuario se niega o se produce un error, el primer argumento del devolución contendrá el error. Si se restaura correctamente, el primer argumento será nulo y el segundo argumento contendrá el valor restaurado.
removeItem(clave[, devolución de llamada])	Función	API de bots 9.0+ Un método que elimina un valor del almacenamiento seguro del dispositivo utilizando la clave especificada. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si se eliminó el valor.
clear([devolución de llamada])	Función	API de bots 9.0+ Un método que borra todas las claves previamente almacenadas por el bot en el almacenamiento seguro del dispositivo. Si es opcional devolución Se pasó el parámetro, el devolución Se llamará a la función. En caso de error, el primer argumento contendrá el error. En caso de éxito, el primer argumento será nulo y el segundo argumento será un valor booleano que indica si se eliminaron todos los valores.
Todos estos métodos devuelven el Almacenamiento seguro objeto, para que puedan encadenarse.

Datos de entrada de la aplicación web
Este objeto contiene datos que se transfieren a la Mini App cuando se abre. Está vacío si la Mini App se lanzó desde un botón del teclado o desde modo en línea.

Campo	Tipo	Descripción
consulta_id	Cadena	Optional. A unique identifier for the Mini App session, required for sending messages via the answerWebAppQuery method.
user	WebAppUser	Optional. An object containing data about the current user.
receiver	WebAppUser	Optional. An object containing data about the chat partner of the current user in the chat where the bot was launched via the attachment menu. Returned only for private chats and only for Mini Apps launched via the attachment menu.
chat	WebAppChat	Optional. An object containing data about the chat where the bot was launched via the attachment menu. Returned for supergroups, channels and group chats – only for Mini Apps launched via the attachment menu.
chat_type	String	Opcional. Tipo de chat desde el que se abrió la Mini App. Puede ser “remitente” para un chat privado con el usuario que abre el enlace, “privado”, “grupo”, “supergrupo” o “canal”. Devuelto solo para Mini Aplicaciones lanzadas desde enlaces directos.
chat_instancia	Cadena	Opcional. Identificador global, correspondiente únicamente al chat desde el que se abrió la Mini App. Devuelto solo para Mini Aplicaciones lanzadas desde un enlace directo.
start_param	Cadena	Opcional. El valor del startattach parámetro, pasado vía enlace. Solo se devuelve para Mini Apps cuando se inicia desde el menú adjunto a través del enlace.

El valor del start_param El parámetro también se pasará en el parámetro GET tgWebAppStartParam, para que la Mini App pueda cargar la interfaz correcta de inmediato.
puede_enviar_después	Entero	Opcional. Tiempo en segundos, después del cual se puede enviar un mensaje a través del respuestaWebAppQuery método.
auth_date	Entero	Hora de Unix en la que se abrió el formulario.
hash	Cadena	Un hash de todos los parámetros pasados, que el servidor bot puede usar para comprobar su validez.
firma NUEVO	Cadena	Una firma de todos los parámetros pasados (excepto hash), que el tercero puede utilizar para comprobar su validez.
Usuario de aplicación web
Este objeto contiene los datos del usuario de la Mini App.

Campo	Tipo	Descripción
id	Entero	A unique identifier for the user or bot. This number may have more than 32 significant bits and some programming languages may have difficulty/silent defects in interpreting it. It has at most 52 significant bits, so a 64-bit integer or a double-precision float type is safe for storing this identifier.
is_bot	Boolean	Optional. True, if this user is a bot. Returns in the receiver field only.
first_name	String	First name of the user or bot.
last_name	String	Optional. Last name of the user or bot.
username	String	Optional. Username of the user or bot.
language_code	String	Optional. IETF language tag of the user's language. Returns in user field only.
is_premium	True	Optional. True, if this user is a Telegram Premium user.
added_to_attachment_menu	True	Optional. True, if this user added the bot to the attachment menu.
allows_write_to_pm	True	Optional. True, if this user allowed the bot to message them.
photo_url	String	Optional. URL of the user’s profile photo. The photo can be in .jpeg or .svg formats.
WebAppChat
This object represents a chat.

Field	Type	Description
id	Integer	Unique identifier for this chat. This number may have more than 32 significant bits and some programming languages may have difficulty/silent defects in interpreting it. But it has at most 52 significant bits, so a signed 64-bit integer or double-precision float type are safe for storing this identifier.
type	String	Type of chat, can be either “group”, “supergroup” or “channel”
title	String	Title of the chat
username	String	Optional. Username of the chat
photo_url	String	Optional. URL of the chat’s photo. The photo can be in .jpeg or .svg formats. Only returned for Mini Apps launched from the attachment menu.
Validating data received via the Mini App
To validate data received via the Mini App, one should send the data from the Telegram.WebApp.initData field to the bot's backend. The data is a query string, which is composed of a series of field-value pairs.

You can verify the integrity of the data received by comparing the received hash parameter with the hexadecimal representation of the HMAC-SHA-256 signature of the data-check-string with the secret key, which is the HMAC-SHA-256 signature of the bot's token with the constant string WebAppData used as a key.

Data-check-string is a chain of all received fields, sorted alphabetically, in the format key=<value> with a line feed character ('\n', 0x0A) used as separator – e.g., 'auth_date=<auth_date>\nquery_id=<query_id>\nuser=<user>'.

The full check might look like:

data_check_string = ...
secret_key = HMAC_SHA256(<bot_token>, "WebAppData")
if (hex(HMAC_SHA256(data_check_string, secret_key)) == hash) {
  // data is from Telegram
}
Para evitar el uso de datos obsoletos, también puede consultar el auth_date campo, que contiene una marca de tiempo de Unix de cuándo fue recibido por la Mini Aplicación.

Una vez validados, los datos podrán ser utilizados en su servidor. Los tipos de datos complejos se representan como objetos serializados en JSON.

Validación de datos para uso de terceros
NUEVO Si necesita compartir los datos con un tercero, este puede validarlos sin necesidad de acceder a su token del bot. Simplemente proporcióneles los datos del Telegram.WebApp.initData campo y tu bot_id.

La integridad de los datos se puede verificar validando los recibidos firma parámetro, que es la representación codificada en base64url del Ed25519 firma del cadena de verificación de datos. La verificación se realiza utilizando la clave pública proporcionada por Telegram.

Cadena de verificación de datos se construye de la siguiente manera:
1. Anteponer el bot_id, seguido de : y la cadena constante WebAppData.
2. Añadir un alimentación de línea personaje ('\n', 0x0A).
3. Agregue todos los campos recibidos (excepto hash y firma), ordenados alfabéticamente, en el formato key=<value>.
4. Separe cada par clave-valor con un carácter de avance de línea ('\n', 0x0A).

Ejemplo:
'12345678:WebAppData\nauth_date=<auth_date>\nquery_id=<query_id>\nuser=<user>'

El proceso de verificación podría verse así:

data_check_string = ...
public_key = "<Telegram_public_key>"
if (Ed25519_verify(public_key, data_check_string, signature)) {
  // data is valid and originated from Telegram
}
Telegram proporciona lo siguiente Ed25519 claves públicas para verificación de firma:

Entorno de prueba: 40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec (hex)
Produc?ia: e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d (hex)

Para evitar el uso de datos obsoletos, el tercero debe validar adicionalmente el auth_date campo. Este campo contiene una marca de tiempo de Unix que indica cuándo la aplicación Mini recibió los datos.

Una vez validados, los datos podrán ser utilizados. Los tipos de datos complejos se representan como objetos serializados en JSON.

Eventos disponibles para mini aplicaciones
La Mini App puede recibir eventos de la aplicación Telegram, a la que se puede conectar un controlador mediante Telegram.WebApp.onEvent(eventType, eventHandler) método. Interior eventHandler el esto objeto se refiere a Telegram.Aplicación web, el conjunto de parámetros enviados al controlador depende del tipo de evento. A continuación se muestra una lista de posibles eventos:

tipo de evento	Descripción
activated NUEVO	API de bots 8.0+ Ocurre cuando la Mini Aplicación se activa (por ejemplo, se abre desde el estado minimizado o se selecciona entre pestañas).
manejador de eventos no recibe parámetros.
deactivated NUEVO	API de bots 8.0+ Ocurre cuando la Mini Aplicación se vuelve inactiva (por ejemplo, se minimiza o se mueve a una pestaña inactiva).
manejador de eventos no recibe parámetros.
themeChanged	Ocurre cada vez que se cambia la configuración del tema en la aplicación Telegram del usuario (incluido el cambio al modo nocturno).
manejador de eventos no recibe parámetros, se pueden recibir nuevas configuraciones de tema y combinación de colores a través de este.themeParams y este.colorScheme respectivamente.
viewportChanged	Ocurre cuando se cambia la sección visible de la Mini App.
manejador de eventos recibe un objeto con un solo campo esEstable en estado. Si esEstable en estado es cierto, el cambio de tamaño de la Mini App ha finalizado. Si es falso, el cambio de tamaño continúa (el usuario está expandiendo o colapsando la Mini App o se está reproduciendo un objeto animado). El valor actual de la altura de la sección visible está disponible en this.viewportHeight.
safeAreaChanged NUEVO	API de bots 8.0+ Ocurre cuando cambian las inserciones del área segura del dispositivo (por ejemplo, debido a un cambio de orientación o ajustes de pantalla).
manejador de eventos no recibe parámetros. Se puede acceder a los valores insertados actuales a través de this.safeAreaInset.
contentSafeAreaChanged NUEVO	API de bots 8.0+ Ocurre cuando el área segura para el contenido cambia (por ejemplo, debido a un cambio de orientación o ajustes de pantalla).
manejador de eventos no recibe parámetros. Se puede acceder a los valores insertados actuales a través de este.contentSafeAreaInset.
mainButtonClicked	Ocurre cuando el botón principal está presionado.
manejador de eventos no recibe parámetros.
secondaryButtonClicked	API de bots 7.10+ Ocurre cuando el botón secundario está presionado.
manejador de eventos no recibe parámetros.
backButtonClicked	API de bots 6.1+ Ocurre cuando el botón de retroceso está presionado.
manejador de eventos no recibe parámetros.
settingsButtonClicked	API de bots 6.1+ Ocurre cuando se presiona el elemento Configuración en el menú contextual.
manejador de eventos no recibe parámetros.
invoiceClosed	API de bots 6.1+ Ocurre cuando se cierra la factura abierta.
manejador de eventos recibe un objeto con los dos campos: url – enlace de factura proporcionado y estatus – uno de los estados de la factura:
- pagado – la factura se pagó exitosamente,
- cancelado – el usuario cerró esta factura sin pagar,
- fallido – el usuario intentó pagar, pero el pago falló,
- pendiente – el pago aún se está procesando. El bot recibirá un mensaje de servicio sobre a pago exitoso cuando el pago se haya realizado correctamente.
popupClosed	API de bots 6.2+ Ocurre cuando se cierra la ventana emergente abierta.
manejador de eventos recibe un objeto con un solo campo botón_id – el valor del campo id del botón presionado. Si no se presionaron botones, el campo botón_id será nulo.
qrTextReceived	API de bots 6.4+ Ocurre cuando el escáner de código QR detecta un código con datos de texto.
manejador de eventos recibe un objeto con un solo campo datos que contiene datos de texto del código QR.
scanQrPopupClosed	API de bots 7.7+ Ocurre cuando el usuario cierra la ventana emergente del escáner de código QR.
manejador de eventos no recibe parámetros.
clipboardTextReceived	API de bots 6.4+ Ocurre cuando el readTextFromClipboard Se llama al método.
manejador de eventos recibe un objeto con un solo campo datos que contiene datos de texto del portapapeles. Si el portapapeles contiene datos que no son de texto, el campo datos será una cadena vacía. Si la Mini App no tiene acceso al portapapeles, el campo datos será nulo.
writeAccessRequested	API de bots 6.9+ Ocurre cuando se solicitó el permiso de escritura.
manejador de eventos recibe un objeto con un solo campo estatus que contiene uno de los estados:
- allowed – el usuario otorgó permiso de escritura al bot,
- cancelado – el usuario rechazó esta solicitud.
contactRequested	API de bots 6.9+ Ocurre cuando se solicitó el número de teléfono del usuario.
manejador de eventos recibe un objeto con un solo campo estatus que contiene uno de los estados:
- enviado – el usuario compartió su número de teléfono con el bot,
- cancelado – el usuario rechazó esta solicitud.
biometricManagerUpdated	API de bots 7.2+ Ocurre cada vez que se cambia el objeto BiometricManager.
manejador de eventos no recibe parámetros.
biometricAuthRequested	API de bots 7.2+ Ocurre siempre que se solicitó autenticación biométrica.
manejador de eventos recibe un objeto con el campo está autenticado que contiene un valor booleano que indica si el usuario se autenticó correctamente. Si está autenticado es cierto, el campo token biométrico contendrá el token biométrico almacenado en un almacenamiento seguro en el dispositivo.
biometricTokenUpdated	API de bots 7.2+ Ocurre cada vez que se actualiza el token biométrico.
manejador de eventos recibe un objeto con un solo campo está actualizado, que contiene un valor booleano que indica si el token se actualizó.
fullscreenChanged NUEVO	API de bots 8.0+ Occurs whenever the Mini App enters or exits fullscreen mode.
eventHandler receives no parameters. The current fullscreen state can be checked via this.isFullscreen.
fullscreenFailed NEW	Bot API 8.0+ Occurs if a request to enter fullscreen mode fails.
eventHandler receives an object with the single field error, describing the reason for the failure. Possible values for error are:
UNSUPPORTED – Fullscreen mode is not supported on this device or platform.
ALREADY_FULLSCREEN – The Mini App is already in fullscreen mode.
homeScreenAdded NEW	Bot API 8.0+ Occurs when the Mini App is successfully added to the home screen.
eventHandler receives no parameters.
homeScreenChecked NEW	Bot API 8.0+ Ocurre después de verificar el estado de la pantalla de inicio.
manejador de eventos recibe un objeto con el campo estatus, que es una cadena que indica el estado actual de la pantalla de inicio. Valores posibles para estatus son:
- unsupported – la función no es compatible y no es posible agregar el ícono a la pantalla de inicio
- desconocido – la función es compatible y se puede agregar el ícono, pero no es posible determinar si el ícono ya se agregó
- añadido – el icono ya se ha añadido a la pantalla de inicio,
- miss – el icono no se ha agregado a la pantalla de inicio.
accelerometerStarted NUEVO	API de bots 8.0+ Ocurre cuando el seguimiento del acelerómetro ha comenzado con éxito.
manejador de eventos no recibe parámetros.
accelerometerStopped NUEVO	API de bots 8.0+ Ocurre cuando el seguimiento del acelerómetro se ha detenido.
manejador de eventos no recibe parámetros.
accelerometerChanged NUEVO	API de bots 8.0+ Ocurre con la frecuencia especificada después de llamar al start método, enviando los datos actuales del acelerómetro.
manejador de eventos no recibe parámetros, los valores de aceleración actuales se pueden recibir mediante esto.x, this.y y esto.z respectivamente.
accelerometerFailed NUEVO	API de bots 8.0+ Ocurre si falla una solicitud para iniciar el seguimiento del acelerómetro.
manejador de eventos recibe un objeto con un solo campo error, describiendo el motivo del fracaso. Valores posibles para error son:
UNSUPPORTED – El seguimiento del acelerómetro no es compatible con este dispositivo o plataforma.
deviceOrientationStarted NUEVO	API de bots 8.0+ Ocurre cuando el seguimiento de la orientación del dispositivo se ha iniciado correctamente.
manejador de eventos no recibe parámetros.
deviceOrientationStopped NUEVO	API de bots 8.0+ Ocurre cuando se detiene el seguimiento de la orientación del dispositivo.
manejador de eventos no recibe parámetros.
deviceOrientationChanged NUEVO	API de bots 8.0+ Ocurre con la frecuencia especificada después de llamar al start método, enviando los datos de orientación actuales.
manejador de eventos no recibe parámetros, los valores de orientación actuales del dispositivo se pueden recibir a través de esto.alfa, esto.beta y esto.gamma respectivamente.
deviceOrientationFailed NUEVO	API de bots 8.0+ Ocurre si falla una solicitud para iniciar el seguimiento de la orientación del dispositivo.
manejador de eventos recibe un objeto con un solo campo error, describiendo el motivo del fracaso. Valores posibles para error son:
UNSUPPORTED – El seguimiento de la orientación del dispositivo no es compatible con este dispositivo o plataforma.
gyroscopeStarted NUEVO	API de bots 8.0+ Ocurre cuando el seguimiento del giroscopio ha comenzado con éxito.
manejador de eventos no recibe parámetros.
gyroscopeStopped NUEVO	API de bots 8.0+ Ocurre cuando el seguimiento del giroscopio se ha detenido.
manejador de eventos no recibe parámetros.
gyroscopeChanged NUEVO	API de bots 8.0+ Ocurre con la frecuencia especificada después de llamar al start método, enviando los datos actuales del giroscopio.
manejador de eventos no recibe parámetros, las velocidades de rotación actuales se pueden recibir mediante esto.x, this.y y esto.z respectivamente.
gyroscopeFailed NUEVO	API de bots 8.0+ Ocurre si falla una solicitud para iniciar el seguimiento del giroscopio.
manejador de eventos recibe un objeto con un solo campo error, describiendo el motivo del fracaso. Valores posibles para error son:
UNSUPPORTED – El seguimiento con giroscopio no es compatible con este dispositivo o plataforma.
locationManagerUpdated NUEVO	API de bots 8.0+ Ocurre cada vez que se cambia el objeto LocationManager.
manejador de eventos no recibe parámetros.
locationRequested NUEVO	API de bots 8.0+ Ocurre cuando se solicitan datos de ubicación.
manejador de eventos recibe un objeto con un solo campo UbicaciónDatos de tipo Datos de ubicación, que contiene la información de ubicación actual.
shareMessageSent NUEVO	API de bots 8.0+ Ocurre cuando el usuario comparte exitosamente el mensaje.
manejador de eventos no recibe parámetros.
shareMessageFailed NUEVO	API de bots 8.0+ Ocurre si falla compartir el mensaje.
manejador de eventos recibe un objeto con un solo campo error, describiendo el motivo del fracaso. Valores posibles para error son:
UNSUPPORTED – La función no es compatible con el cliente.
MENSAJE_VENCIDO – No se pudo recuperar el mensaje porque ha caducado.
MENSAJE_ENVIAR_FALLÓ – Se produjo un error al intentar enviar el mensaje.
USUARIO_DECLINADO – El usuario cerró el cuadro de diálogo sin compartir el mensaje.
ERROR_DESCONOCIDO – Se produjo un error desconocido.
emojiStatusSet NUEVO	API de bots 8.0+ Ocurre cuando el estado del emoji se establece correctamente.
manejador de eventos no recibe parámetros.
emojiStatusFailed NUEVO	API de bots 8.0+ Ocurre si falla la configuración del estado del emoji.
manejador de eventos recibe un objeto con un solo campo error, describiendo el motivo del fracaso. Valores posibles para error son:
UNSUPPORTED – La función no es compatible con el cliente.
EMOJI_SUGERIDO_INVÁLIDO – Uno o más identificadores de emoji no son válidos.
DURACIÓN_INVÁLIDA – La duración especificada no es válida.
USUARIO_DECLINADO – El usuario cerró el cuadro de diálogo sin establecer un estado.
ERROR_SERVIDOR – Se produjo un error del servidor al intentar configurar el estado.
ERROR_DESCONOCIDO – Se produjo un error desconocido.
emojiStatusAccessRequested NUEVO	API de bots 8.0+ Ocurre cuando se solicitó el permiso de escritura.
manejador de eventos recibe un objeto con un solo campo estatus que contiene uno de los estados:
- allowed – el usuario otorgó permiso de estado de emoji al bot,
- cancelado – el usuario rechazó esta solicitud.
fileDownloadRequested NUEVO	API de bots 8.0+ Ocurre cuando el usuario responde a la solicitud de descarga del archivo.
manejador de eventos recibe un objeto con un solo campo estatus que contiene uno de los estados:
- descargando – la descarga del archivo ha comenzado,
- cancelado – el usuario rechazó esta solicitud.
Agregar bots al menú adjunto
La integración del menú adjunto actualmente solo está disponible para los principales anunciantes en el Plataforma de anuncios de Telegram. Sin embargo, Todos los bots Puedes usarlo en el probar el entorno del servidor. Hable con Botfather en el servidor de prueba para configurar la integración.

Se utiliza un enlace especial para agregar bots al menú adjunto:

https://t.me/botusername?startattach
o
https://t.me/botusername?startattach=command

Por ejemplo, abre esto enlace del menú adjunto para @DurgerKingBot, luego usa el Adjuntar menú en cualquiera chat privado.

Al abrir el enlace, el usuario solicita que agregue el bot a su menú adjunto. Si el bot ya se agregó, el menú adjunto se abrirá en el chat actual y redirigirá al bot allí (si el enlace se abre desde un chat 1 a 1). Si no está vacío startattach El parámetro se incluyó en el enlace, se pasará a la Mini App en el start_param campo y en el parámetro GET tgWebAppStartParam.

También se admiten los siguientes formatos de enlace:

https://t.me/username?attach=botusername
https://t.me/username?attach=botusername&startattach=command
https://t.me/+1234567890?attach=botusername
https://t.me/+1234567890?attach=botusername&startattach=command

Estos enlaces abren la Mini App en el menú adjunto del chat con un usuario específico. Si el bot aún no se agregó al menú adjunto, se le solicitará al usuario que lo haga. Si no está vacío startattach El parámetro se incluyó en el enlace, se pasará a la Mini App en el start_param campo y en el parámetro GET tgWebAppStartParam.

API de bots 6.1+admite un nuevo formato de enlace:

https://t.me/botusername?startattach&choose=users+bots
https://t.me/botusername?startattach=command&choose=groups+channels

Al abrir dicho enlace, se solicita al usuario que elija un chat específico y se abre el menú adjunto en ese chat. Si el bot aún no se agregó al menú adjunto, se le solicitará al usuario que lo haga. Puede especificar entre qué tipos de chats podrá elegir el usuario. Puede ser uno o más de los siguientes tipos: usuarios, bots, grupos, canales separados por a + signo. Si no está vacío startattach El parámetro se incluyó en el enlace, se pasará a la Mini App en el start_param campo y en el parámetro GET tgWebAppStartParam.

Datos adicionales en el agente de usuario
Cuando la Mini Aplicación se ejecuta en Android, se agrega información adicional a la cadena User-Agent para proporcionar más contexto sobre el entorno de la aplicación. Esta información incluye la versión de la aplicación, el modelo del dispositivo, la versión de Android, la versión del SDK y la clase de rendimiento del dispositivo, con el siguiente formato:

Telegram-Android/{app_version} ({manufacturer} {model}; Android {android_version}; SDK {sdk_version}; {performance_class})
unde:

{versión_aplicación} es la versión de la aplicación Telegram (por ejemplo, 11.3.3),
{fabricante} {modelo} representa el fabricante y el modelo del dispositivo (por ejemplo, Google sdk_gphone64_arm64),
{versión_android} es la versión del sistema operativo Android que se ejecuta en el dispositivo (por ejemplo, 14),
{versión_sdk} indica la versión del SDK de Android (por ejemplo, 34),
{clase_rendimiento} especifica la clase de rendimiento del dispositivo como LOW, AVERAGE, o HIGH, indicando la capacidad de rendimiento del dispositivo.
Ejemplo
Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.136 Mobile Safari/537.36 Telegram-Android/11.3.3 (Google sdk_gphone64_arm64; Android 14; SDK 34; LOW)

Recomendamos utilizar esta información para optimizar su Mini App en función de las capacidades del dispositivo. Por ejemplo, puedes ajustar animaciones y efectos visuales en juegos en dispositivos de bajo rendimiento para garantizar una experiencia fluida para todos los usuarios, independientemente de las especificaciones del dispositivo.

Probando mini aplicaciones
Uso de bots en el entorno de prueba
Para iniciar sesión en el entorno de prueba, utilice cualquiera de los siguientes:

iOS: toque 10 veces en el ícono Configuración > Cuentas > Iniciar sesión en otra cuenta > Prueba.
Escritorio de Telegram: abra ? Configuración > Shift + Alt + Haga clic derecho ‘Agregar cuenta’ y seleccione ‘Servidor de prueba’.
macOS: click the Settings icon 10 times to open the Debug Menu, ? + click ‘Add Account’ and log in via phone number.
The test environment is completely separate from the main environment, so you will need to create a new user account and a new bot with @BotFather.

After receiving your bot token, you can send requests to the Bot API in this format:

https://api.telegram.org/bot<token>/test/METHOD_NAME
Note: When working with the test environment, you may use HTTP links without TLS to test your Mini App.

Debug Mode for Mini Apps
Use these tools to find app-specific issues in your Mini App:

iOS

In Telegram tap 10 times on the Settings icon and toggle on Allow Web View Inspection.
Connect your phone to your computer using a USB cable.
Abra Safari en su Mac y luego vaya a Desarrollar > [Nombre de su dispositivo] en la barra de menú.
Inicia tu Mini App en el dispositivo iOS – aparecerá en el Desarrollar menú debajo de tu dispositivo.
Android

Habilitar depuración USB en tu dispositivo.
En Configuración de Telegram, desplácese hasta el final, mantenga presionado el botón número de versión dos veces.
Elige Habilitar la depuración de WebView en la configuración de depuración.
Conecta tu teléfono a tu computadora y ábrelo chrome://inspect/#devices En Chrome – verás tu Mini App allí cuando la inicies en tu teléfono.
Telegram Desktop en Windows y Linux

Download and launch the Beta Version of Telegram Desktop on Windows or Linux (not supported on Telegram Desktop for macOS yet).
Go to Settings > Advanced > Experimental settings > Enable webview inspection.
Right click in the WebView and choose Inspect.
Telegram macOS

Download and launch the Beta Version of Telegram macOS.
Quickly click 5 times on the Settings icon to open the debug menu and enable “Debug Mini Apps”.
Right click in the Mini App and choose Inspect Element.
Telegram
Telegram es una app de mensajería en la nube para móviles y computadoras con foco en la seguridad y la velocidad.
Acerca de
FAQ
Privacidad
Prensa
Aplicaciones móviles
iPhone/iPad
Android
Móvil web
Para computadora
PC/Mac/Linux
macOS
Navegador web
Plataforma
API
Traducciones
Vista rápida
Ir arriba
# [2.0.0](https://github.com/DaniMancillaDev/Bot_calidad/compare/v1.0.0...v2.0.0) (2026-07-27)


* feat!: release v2.0.0 - refactor arquitectural completo ([67fb05d](https://github.com/DaniMancillaDev/Bot_calidad/commit/67fb05d475e0f0651738f8e89f2a64a0663bc4f4))


### Bug Fixes

* **api:** clear FSM state in Redis on session cleanup ([8641078](https://github.com/DaniMancillaDev/Bot_calidad/commit/8641078028952f44c7037e747caff37080eaa425))
* sync excel reports, add rules, extend dl limit ([be5cafc](https://github.com/DaniMancillaDev/Bot_calidad/commit/be5cafcdf2d3057eeea369ddf0f9b3de0862ec63))
* sync reportes, fechas excel y diccionario ([251127f](https://github.com/DaniMancillaDev/Bot_calidad/commit/251127f12deb73805e2541adf15ad502a2622aba))
* usar ContadorUsuario y esperar listo en Redis ([b229a01](https://github.com/DaniMancillaDev/Bot_calidad/commit/b229a01a05335d6bc5bf7404e6e427e0d18b6792))


### Features

* **ai:** implementar traductor deterministico v1.5 ([6efe105](https://github.com/DaniMancillaDev/Bot_calidad/commit/6efe105df04c976e3a09f51c90954f438995bac1))
* **arch:** implement Phase 1 enterprise infrastructure evolution ([a86734a](https://github.com/DaniMancillaDev/Bot_calidad/commit/a86734a318a4d029519968b30e96217e71923232))
* **bot/web:** estabilizar bot y optimizar pipeline de reportes ([fe5bf8d](https://github.com/DaniMancillaDev/Bot_calidad/commit/fe5bf8de8c4102edba176b1b473821ebbab9353c))
* **bot:** agregar comando /reporte_turno para admin ([b972851](https://github.com/DaniMancillaDev/Bot_calidad/commit/b9728516e686f3adfdb3008d5a015da9ae8af5c3))
* **bot:** remove piezas defectuosas from /estado ([59e77cb](https://github.com/DaniMancillaDev/Bot_calidad/commit/59e77cbe4b0a4e217439db3d5f90c96da37028f5))
* **calidad:** agregar exclusión de fotos en V2 ([7424edf](https://github.com/DaniMancillaDev/Bot_calidad/commit/7424edfb085bc70776bccdea0c8b08a0592ccb9c))
* **calidad:** implement async excel generation and record editing ([f1f0efb](https://github.com/DaniMancillaDev/Bot_calidad/commit/f1f0efb6bc873bbe3c4b08136cec88c2e9526214))
* **calidad:** migrar _parse_fotos_nums a photo_parser resolviendo bug de rangos ([8549f5d](https://github.com/DaniMancillaDev/Bot_calidad/commit/8549f5d686e273044c34913ccbf8a89c9186623f))
* **reportes:** consolidar registros y generar pptx automatico ([3f9c66b](https://github.com/DaniMancillaDev/Bot_calidad/commit/3f9c66b9df78e47d634cb0a66d94b37208fd9ed1))
* **web:** agrupar registros por usuario ([0617e0a](https://github.com/DaniMancillaDev/Bot_calidad/commit/0617e0a7cf050c739ee9e2415c5db9064e059edf))
* **web:** update settings for ngrok and fix session / export logic ([6a85c50](https://github.com/DaniMancillaDev/Bot_calidad/commit/6a85c50f80df955084ac3ef2688a664b92cd0881))


### BREAKING CHANGES

* refactor interno completo de arquitectura, optimización del pipeline de procesamiento y cambios en el flujo de despliegue.

# 1.0.0 (2026-05-04)


### Bug Fixes

* **bot:** estabilizar pipeline de multimedia y eliminar spam ([1cf2b2c](https://github.com/DaniMancillaDev/Bot_calidad/commit/1cf2b2c265123d6cc62063f8bbdf0d2f2a7bd4c2))
* **bot:** estabilizar pipeline de multimedia y eliminar spam ([ac1134a](https://github.com/DaniMancillaDev/Bot_calidad/commit/ac1134a55093eb1a13db8f8ef7d118fc02e834c7))
* **ci:** corregir warnings de Node.js 20 en Actions ([1080724](https://github.com/DaniMancillaDev/Bot_calidad/commit/108072444cac3c48764d1767a3185b4aa7097b6d))


### Features

* **deploy:** preparar infraestructura para produccion VPS ([bbb5328](https://github.com/DaniMancillaDev/Bot_calidad/commit/bbb53287bfaa026795b8021b61455c1a41a2740c))
* reemplazar print() por logging centralizado ([7ebcfea](https://github.com/DaniMancillaDev/Bot_calidad/commit/7ebcfea6ca404e69b3910b65bcf87475d6b9f4cf))


### Performance Improvements

* **db:** agregar indices y borrar tablas muertas ([2670568](https://github.com/DaniMancillaDev/Bot_calidad/commit/2670568cabe3e320d2202bacf0d7cf305cccc4e9))

## [1.2.1](https://github.com/DaniMancillaDev/Bot_calidad/compare/v1.2.0...v1.2.1) (2026-05-04)


### Performance Improvements

* **db:** agregar indices y borrar tablas muertas ([2670568](https://github.com/DaniMancillaDev/Bot_calidad/commit/2670568cabe3e320d2202bacf0d7cf305cccc4e9))

# [1.2.0](https://github.com/DaniMancillaDev/Bot_calidad/compare/v1.1.0...v1.2.0) (2026-05-04)


### Features

* **deploy:** preparar infraestructura para produccion VPS ([bbb5328](https://github.com/DaniMancillaDev/Bot_calidad/commit/bbb53287bfaa026795b8021b61455c1a41a2740c))

# [1.1.0](https://github.com/DaniMancillaDev/Bot_calidad/compare/v1.0.0...v1.1.0) (2026-05-04)


### Features

* reemplazar print() por logging centralizado ([7ebcfea](https://github.com/DaniMancillaDev/Bot_calidad/commit/7ebcfea6ca404e69b3910b65bcf87475d6b9f4cf))

# 1.0.0 (2026-05-04)


### Bug Fixes

* **ci:** corregir warnings de Node.js 20 en Actions ([1080724](https://github.com/DaniMancillaDev/Bot_calidad/commit/108072444cac3c48764d1767a3185b4aa7097b6d))

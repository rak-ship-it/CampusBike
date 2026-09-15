<img src="../IMG/diagramaDb.png">

# Proyecto hecho por Jhoan Landazabal y Valentina Rivera

# Casos de Uso para la Base de Datos

## Caso de Uso 1: Gestión de Inventario de Bicicletas

Descripción: Este caso de uso describe cómo el sistema gestiona el inventario de bicicletas,
permitiendo agregar nuevas bicicletas, actualizar la información existente y eliminar bicicletas que
ya no están disponibles.
Actores:
Administrador de Inventario

Flujo Principal:
1. El administrador de inventario ingresa al sistema.
2. El administrador selecciona la opción para agregar una nueva bicicleta.
3. El administrador ingresa los detalles de la bicicleta (modelo, marca, precio, stock).

```sql
CALL agregarBicicleta("BMX-32","BMX","120000","20");
```

4. El sistema valida y guarda la información de la nueva bicicleta.

```sql

DELIMITER $$
DROP TRIGGER IF EXISTS stockNegativoIns $$
CREATE TRIGGER stockNegativoIns
BEFORE INSERT ON bicicleta
FOR EACH ROW
BEGIN
    IF NEW.stock < 0 OR NEW.precio < 0 THEN -- Si se inserta un valor negativo para el stock --
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El "STOCK" y el "PRECIO" no pueden ser negativo'; -- Enviar un mensaje --
    END IF;
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS agregarBicicleta$$
CREATE PROCEDURE agregarBicicleta(
    IN newModelo VARCHAR(255),
    IN newMarca VARCHAR(255),
    IN newPrecio DECIMAL(10, 2),
    IN newStock INT
)
BEGIN
    -- Insertar la nueva bicicleta en la tabla bicicleta --
    INSERT INTO bicicleta (modelo, marca, precio, stock)
    VALUES (newModelo, newMarca, newPrecio, newStock);
END$$
DELIMITER ;
```

5. El administrador selecciona una bicicleta existente para actualizar.
6. El administrador actualiza la información (precio, stock).

```sql
CALL actualizarBicicleta(1,"280000","15");
```


7. El sistema valida y guarda los cambios.

```sql
DELIMITER $$
DROP TRIGGER IF EXISTS stockNegativoUpd$$
CREATE TRIGGER stockNegativoUpd
BEFORE UPDATE ON bicicleta
FOR EACH ROW
BEGIN
    IF NEW.stock < 0 OR NEW.precio < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El "STOCK" y el "PRECIO" no pueden ser negativo';
    END IF;
END $$
DELIMITER ;
```

8. El administrador selecciona una bicicleta para eliminar.

```sql
CALL eliminarBicicleta(1)
```

9. El sistema elimina la bicicleta seleccionada del inventario.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS eliminarBicicleta$$
CREATE PROCEDURE eliminarBicicleta(
    IN inBicicletaId INT
)
BEGIN
    -- Eliminar la bicicleta de la tabla Bicicletas --
    DELETE FROM bicicleta
    WHERE id = inBicicletaID;
END $$
DELIMITER ;

```

## Caso de Uso 2: Registro de Ventas

Descripción: Este caso de uso describe el proceso de registro de una venta de bicicletas,
incluyendo la creación de una nueva venta, la selección de las bicicletas vendidas y el cálculo del
total de la venta.
Actores:
Vendedor

Flujo Principal:
1. El vendedor ingresa al sistema.
2. El vendedor selecciona la opción para registrar una nueva venta.
3. El vendedor selecciona el cliente que realiza la compra.

```sql
-- El "@VentaId" es una variable que va a guardar
-- El id de venta que se genera para esta nueva venta
CALL registrarVenta("001",@VentaId);

DELIMITER $$
DROP PROCEDURE IF EXISTS registrarVenta$$
CREATE PROCEDURE registrarVenta(
    IN inClienteId VARCHAR(10),
    OUT outVentaId INT
)
BEGIN
    /* Se crea una nueva venta con total inicial de 0
        para que luego el sistema calcule el total en
        base a los detalles de la venta */
    INSERT INTO venta(fecha,clienteId,total)
    VALUES (NOW(), inClienteId, 0);

    /* Se saca el valor del id para utilizarlo luego */
    SET outVentaId = LAST_INSERT_ID();
END $$
DELIMITER ;

```

4. El vendedor selecciona las bicicletas que el cliente desea comprar y especifica la cantidad.

```sql
CALL registrarDetalleVenta(@VentaId,1,10);
```

5. El sistema calcula el total de la venta.

```sql
    -- Obtener el precio unitario de la bicicleta --
    SELECT precio INTO precioUnitario
    FROM bicicleta
    WHERE id = inBicicletaId;

    -- Calcular el total del detalle --
    SET totalDetalle = precioUnitario * inCantidad;

        -- Actualizar el total de la venta --
    UPDATE venta
    SET total = totalDetalle
    WHERE id = inVentaId;

```

6. El vendedor confirma la venta.
7. El sistema guarda la venta y actualiza el inventario de bicicletas.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS registrarDetalleVenta$$
CREATE PROCEDURE RegistrarDetalleVenta(
    IN inVentaId INT,
    IN inBicicletaId INT,
    IN inCantidad INT
)
BEGIN
    DECLARE precioUnitario DECIMAL(10, 2);
    DECLARE totalDetalle DECIMAL(10, 2);

    -- Obtener el precio unitario de la bicicleta --
    SELECT precio INTO precioUnitario
    FROM bicicleta
    WHERE id = inBicicletaId;

    -- Calcular el total del detalle --
    SET totalDetalle = precioUnitario * inCantidad;

    -- Insertar el detalle de la venta --
    INSERT INTO detalleVenta (ventaId, bicicletaId, cantidad, precioUnitario)
    VALUES (inVentaId, inBicicletaId, inCantidad, precioUnitario);

    -- Actualizar el total de la venta --
    UPDATE venta
    SET total = totalDetalle
    WHERE id = inVentaId;

    -- Actualizar el inventario de bicicletas --
    UPDATE bicicleta
    SET stock = stock - inCantidad
    WHERE id = inBicicletaId;
END $$
DELIMITER ;

```

## Caso de Uso 3: Gestión de Proveedores y Repuestos

Descripción: Este caso de uso describe cómo el sistema gestiona la información de proveedores y
repuestos, permitiendo agregar nuevos proveedores y repuestos, actualizar la información
existente y eliminar proveedores y repuestos que ya no están activos.
Actores:
Administrador de Proveedores
Flujo Principal:

1. El administrador de proveedores ingresa al sistema.
2. El administrador selecciona la opción para agregar un nuevo proveedor.
3. El administrador ingresa los detalles del proveedor (nombre, contacto, teléfono, correo
electrónico, ciudad).

```sql
CALL agregarProveedor("nombre","contacto","telefono","correo",1);
```

4. El sistema valida y guarda la información del nuevo proveedor.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS agregarProveedor$$
CREATE PROCEDURE agregarProveedor (
    IN inNombreProveedor VARCHAR(50),
    IN inNombreContacto VARCHAR(50),
    IN inTelefono VARCHAR(20),
    IN inCorreo VARCHAR(100),
    IN inCiudadId INT
)
BEGIN
    DECLARE proveedorExistente INT;

    SELECT COUNT(p.id) INTO proveedorExistente
    FROM proveedor p
    WHERE p.nombre = inNombreProveedor
    IF proveedorExistente = 0 THEN
        INSERT INTO proveedor (nombre, contacto, telefono, correo, ciudadId)
        VALUES (inNombreProveedor, inNombreContacto, inTelefono, inCorreo, inCiudadId);
    ELSE
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El proveedor ya existe con el mismo nombre, teléfono o correo electrónico';
    END IF;

END $$
DELIMITER ;
```

5. El administrador selecciona la opción para agregar un nuevo repuesto.

6. El administrador ingresa los detalles del repuesto (nombre, descripción, precio, stock,
proveedor).

```sql
CALL agregarRepuesto("nombre","descripcion",20000,30,1);
```

7. El sistema valida y guarda la información del nuevo repuesto.

```sql
DROP PROCEDURE IF EXISTS agregarRepuesto$$
CREATE PROCEDURE agregarRepuesto(
IN inNombreRepuesto VARCHAR(20),
IN inDescripcionRepuesto TEXT,
IN inPrecio DOUBLE,
IN inStock INT,
IN inProveedorId INT
)
BEGIN
-- Valida que el nombre del repuesto no esté vacío
IF inNombreRepuesto IS NULL OR inNombreRepuesto = '' THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El nombre del repuesto no puede estar vacío';
END IF;

-- Valida que el precio sea mayor que 0
IF inPrecio <= 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El precio debe ser mayor que 0';
END IF;

-- Valida que el stock sea mayor o igual que 0
IF inStock < 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El stock no puede ser negativo';
END IF;

-- Valida que el proveedor exista
IF (SELECT COUNT(id) FROM proveedor WHERE id = inProveedorId) = 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El proveedor no existe';
END IF;

-- Inserta el nuevo repuesto si todas las validaciones pasan
INSERT INTO repuesto (nombre, descripcion, precio, stock, proveedorId)
VALUES (inNombreRepuesto, inDescripcionRepuesto, inPrecio, inStock, inProveedorId);
END $$

DELIMITER ;
```

8. El administrador selecciona un proveedor existente para actualizar.
9. El administrador actualiza la información del proveedor.

```sql
CALL actualizarProveedor(1,"nombre","contacto","telefono","correo",1);
```

10. El sistema valida y guarda los cambios.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS actualizarProveedor$$
CREATE PROCEDURE actualizarProveedor(
    IN inId INT,
    IN inNombre VARCHAR(20),
    IN inContacto VARCHAR(20),
    IN inTelefono VARCHAR(15),
    IN inCorreo VARCHAR(50),
    IN inCiudadId INT
)
BEGIN
	-- Valida que el proveedor exista
	IF (SELECT COUNT(id) FROM proveedor WHERE id = inId) = 0 THEN
		SIGNAL SQLSTATE '45000'
		SET MESSAGE_TEXT = 'El proveedor no existe';
	END IF;

	-- Valida que el nombre del proveedor no esté vacío
	IF inNombre IS NULL OR inNombre = '' THEN
		SIGNAL SQLSTATE '45000'
		SET MESSAGE_TEXT = 'El nombre del proveedor no puede estar vacío';
	END IF;

	-- Valida que el nombre del contacto no esté vacío
	IF inContacto IS NULL OR inContacto = '' THEN
		SIGNAL SQLSTATE '45000'
		SET MESSAGE_TEXT = 'El nombre del contacto no puede estar vacío';
	END IF;

	-- Valida que el teléfono no esté vacío y sea único
	IF inTelefono IS NULL OR inTelefono = '' THEN
		SIGNAL SQLSTATE '45000'
		SET MESSAGE_TEXT = 'El teléfono no puede estar vacío';
	ELSEIF (SELECT COUNT(id) FROM proveedor WHERE telefono = inTelefono AND id <> inId) > 0 THEN
		SIGNAL SQLSTATE '45000'
		SET MESSAGE_TEXT = 'El teléfono ya está en uso por otro proveedor';
	END IF;

	-- Valida que el correo electrónico no esté vacío y sea único
	IF inCorreo IS NULL OR inCorreo = '' THEN
		SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El correo electrónico no puede estar vacío';
	ELSEIF (SELECT COUNT(id) FROM proveedor WHERE correo = inCorreo AND id = inId) > 0 THEN
		SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El correo electrónico ya está en uso por otro proveedor';
	END IF;

	-- Valida que la ciudad exista
	IF (SELECT COUNT(id) FROM ciudad WHERE id = inCiudadId) = 0 THEN
		SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La ciudad no existe';
	END IF;


	UPDATE proveedor
	SET nombre = inNombre,
		contacto = inContacto,
		telefono = inTelefono,
		correo = inCorreo,
		ciudadId = inCiudadId
	WHERE id = inId;
END $$

DELIMITER ;
```


11. El administrador selecciona un repuesto existente para actualizar.
12. El administrador actualiza la información del repuesto.

```sql
CALL actualizarRepuesto(1,"nombre","descripcion",10000,10,1);
```

13. El sistema valida y guarda los cambios.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS actualizarRepuesto$$
CREATE PROCEDURE actualizarRepuesto(
    IN inId INT,
    IN inNombre VARCHAR(20),
    IN inDescripcion TEXT,
    IN inPrecio DOUBLE,
    IN inStock INT,
    IN inProveedorId INT
)
BEGIN
-- Valida que el repuesto exista
IF (SELECT COUNT(id) FROM repuesto WHERE id = inId) = 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El repuesto no existe';
END IF;

-- Valida que el nombre del repuesto no esté vacío
IF inNombre IS NULL OR inNombre = '' THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El nombre del repuesto no puede estar vacío';
END IF;

-- Valida que el precio sea mayor que 0
IF inPrecio <= 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El precio debe ser mayor que 0';
END IF;

-- Valida que el stock no sea negativo
IF inStocl < 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El stock no puede ser negativo';
END IF;

-- Valida que el proveedor exista
IF (SELECT COUNT(id) FROM proveedor WHERE id = inProveedorId) = 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El proveedor no existe';
END IF;

-- Actualiza el repuesto si todas las validaciones pasan
UPDATE repuesto
SET nombre = inNombre,
    descripcion = inDescripcion,
    precio = inPrecio,
    stock = inStock,
    proveedorId = inProveedorId
WHERE id = inId;
END $$

DELIMITER ;
```


14. El administrador selecciona un proveedor para eliminar.

```sql
CALL eliminarProveedor(1);
```

15. El sistema elimina el proveedor seleccionado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS eliminarProveedor$$
CREATE PROCEDURE eliminarProveedor(
    IN inId INT
)
BEGIN
    DECLARE proveedorExistente INT;

    -- Valida que el proveedor exista
    SELECT COUNT(id) INTO proveedorExistente
    FROM proveedor
    WHERE id = inId;

    IF proveedorExistente = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El proveedor no existe';
    END IF;

    -- Elimina repuestos asociados al proveedor
    DELETE FROM repuesto WHERE proveedorId = inId;

    -- Elimina compras asociadas al proveedor
    DELETE FROM compra WHERE proveedorId = inId;

    -- Elimina el proveedor
    DELETE FROM proveedor WHERE id = inId;
    END $$

DELIMITER ;

```

16. El administrador selecciona un repuesto para eliminar.

```sql
CALL eliminarRepuesto(1);
```

17. El sistema elimina el repuesto seleccionado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS eliminarRepuesto$$
CREATE PROCEDURE eliminarRepuesto(
    IN inId INT
)
BEGIN
    DECLARE repuestoExistente INT;

    -- Valida que el repuesto exista
    SELECT COUNT(id) INTO repuestoExistente
    FROM repuesto
    WHERE id = inId;

    IF repuestoExistente = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El repuesto no existe';
    END IF;

    -- Elimina registros relacionados en detalle_venta
    DELETE FROM detalleVenta WHERE repuestoId = inId;

    -- Elimina registros relacionados en detalle_compra
    DELETE FROM detalleCompra WHERE repuestoId = inId;

    -- Elimina el repuesto
    DELETE FROM repuesto WHERE id = inId;
END $$
DELIMITER ;

```

## Caso de Uso 4: Consulta de Historial de Ventas por Cliente

Descripción: Este caso de uso describe cómo el sistema permite a un usuario consultar el
historial de ventas de un cliente específico, mostrando todas las compras realizadas por el cliente
y los detalles de cada venta.
Actores:
Vendedor
Administrador
Flujo Principal:

1. El usuario ingresa al sistema.
2. El usuario selecciona la opción para consultar el historial de ventas.
3. El usuario selecciona el cliente del cual desea ver el historial.

```sql
CALL mostrarHistorialVentas("clienteId");
```

4. El sistema muestra todas las ventas realizadas por el cliente seleccionado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS mostrarHistorialVentas$$
CREATE PROCEDURE mostrarHistorialVentas(
    IN inClienteID INT
)
BEGIN
    /*
        Se hace uso de una consulta que devuelve
        el id, la fecha y el total de todas
        las ventas cuyo cliente coincida con
        el id del cliente que recibe el procedure
    */
    SELECT v.id AS ventaID, v.fecha, v.total
    FROM venta v
    WHERE v.clienteId = inClienteId
    ORDER BY v.fecha DESC;
END $$
DELIMITER ;
```

5. El usuario selecciona una venta específica para ver los detalles.

```sql
CALL consultarDetallesVenta(1);
```

6. El sistema muestra los detalles de la venta seleccionada (bicicletas compradas, cantidad,
precio).

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS consultarDetallesVenta$$
CREATE PROCEDURE consultarDetallesVenta(
    IN inVentaId INT
)
BEGIN
    /*
        Se hace uso de una consulta para
        sacar los detalles de la venta usando el
        id de venta que recibe el procedure

        Además se hace uso del join para mostrar
        detalles de la bicicleta que se vende
    */
    SELECT dv.bicicletaId, b.modelo, b.marca, dv.cantidad, dv.precioUnitario
    FROM detalleVenta dv
    JOIN bicicleta b ON dv.bicicletaId = b.id
    WHERE dv.ventaId = inVentaId;
END $$
DELIMITER ;
```

## Caso de Uso 5: Gestión de Compras de Repuestos

Descripción: Este caso de uso describe cómo el sistema gestiona las compras de repuestos a
proveedores, permitiendo registrar una nueva compra, especificar los repuestos comprados y
actualizar el stock de repuestos.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona la opción para registrar una nueva compra.
3. El administrador selecciona el proveedor al que se realizó la compra.
4. El administrador ingresa los detalles de la compra (fecha, total).

```sql
CALL registrarCompra("fecha",1,20000,@compraId);
```

5. El sistema guarda la compra y genera un identificador único.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS registrarCompra$$
CREATE PROCEDURE registrarCompra(
    IN inFecha DATE,
    IN inProveedorId INT,
    IN inTotal DECIMAL(10, 2),
    OUT outCompraId INT
)
BEGIN
    -- Crear una nueva compra --
    INSERT INTO compra (fecha, proveedorId, total)
    VALUES (inFecha, inProveedorId, inTotal);

    -- Obtener el ID de la nueva compra creada --
    SET outCompraId = LAST_INSERT_ID();
END $$
DELIMITER ;

```

6. El administrador selecciona los repuestos comprados y especifica la cantidad y el precio
unitario.

```sql
CALL registrarDetalleCompra(@compraId,2,10,20000);
```

7. El sistema guarda los detalles de la compra y actualiza el stock de los repuestos comprados.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS registrarDetalleCompra$$
CREATE PROCEDURE registrarDetalleCompra(
    IN inCompraId INT,
    IN inRepuestoId INT,
    IN inCantidad INT,
    IN inPrecioUnitario DECIMAL(10, 2)
)
BEGIN
    DECLARE totalDetalle DECIMAL(10, 2);

    SET totalDetalle = inPrecioUnitario * inCantidad;

    INSERT INTO detalleCompra (compraId, repuestoId, cantidad, precioUnitario)
    VALUES (inCompraId, inRepuestoId, inCantidad, inPrecioUnitario);

    UPDATE repuesto
    SET stock = stock + inCantidad
    WHERE id = inRepuestoId;

    UPDATE compra
    SET total = total + totalDetalle
    WHERE id = inCompraId;
END $$
DELIMITER ;
```

# Casos de Uso con Subconsultas

## Caso de Uso 6: Consulta de Bicicletas Más Vendidas por Marca

Descripción: Este caso de uso describe cómo el sistema permite a un usuario consultar las
bicicletas más vendidas por cada marca.
Actores:
Vendedor
Administrador
Flujo Principal:

1. El usuario ingresa al sistema.
2. El usuario selecciona la opción para consultar las bicicletas más vendidas por marca.

```sql
SELECT
        b.marca,
        b.modelo,
        SUM(dv.cantidad) AS total_vendido
    FROM
        bicicleta b
    JOIN
        detalleVenta dv ON b.Id = dv.bicicletaId
    GROUP BY
        b.marca, b.modelo
    HAVING
        SUM(dv.cantidad) = (
            SELECT
                MAX(total_vendido)
            FROM (
                SELECT
                    b2.marca,
                    b2.modelo,
                    SUM(dv2.cantidad) AS total_vendido
                FROM
                    bicicleta b2
                JOIN
                    detalleVenta dv2 ON b2.Id = dv2.bicicletaId
                GROUP BY
                    b2.marca, b2.modelo
            ) AS subquery
            WHERE subquery.marca = b.marca
        )
    ORDER BY
        total_vendido DESC;
```

3. El sistema muestra una lista de marcas y el modelo de bicicleta más vendido para cada
marca.

```sql
+-------------+--------------+---------------+
| marca       | modelo       | total_vendido |
+-------------+--------------+---------------+
| Specialized | Mountain X   |             1 |
| Trek        | Roadster Pro |             1 |
+-------------+--------------+---------------+
```

## Caso de Uso 7: Clientes con Mayor Gasto en un Año Específico

Descripción: Este caso de uso describe cómo el sistema permite consultar los clientes que han
gastado más en un año específico.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para consultar los clientes con mayor gasto en un año
específico.
3. El administrador ingresa el año deseado.

```sql
 SELECT
        c.id AS ClienteID,
        c.nombre AS nombre,
        SUM(v.Total) AS TotalGastado
    FROM
        cliente c
    JOIN
        venta v ON c.id = v.clienteId
    WHERE
        YEAR(v.fecha) = 2024
    GROUP BY
        c.id, c.nombre
    ORDER BY
        TotalGastado DESC;
```

4. El sistema muestra una lista de los clientes que han gastado más en ese año, ordenados por
total gastado.

```sql
+-----------+------------+--------------+
| ClienteID | nombre     | TotalGastado |
+-----------+------------+--------------+
| 001       | Juan Pérez |      1800.00 |
| 002       | Ana Gómez  |       800.00 |
+-----------+------------+--------------+
```

## Caso de Uso 8: Proveedores con Más Compras en el Último Mes

Descripción: Este caso de uso describe cómo el sistema permite consultar los proveedores que
han recibido más compras en el último mes.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona la opción para consultar los proveedores con más compras en el
último mes.

```sql
SELECT p.nombre, sub.comprasProveedor
FROM proveedor p
JOIN (
    SELECT proveedorId, COUNT(c.id) AS comprasProveedor
    FROM compra c
    WHERE MONTH(c.fecha) = 7
    GROUP BY c.proveedorId
) sub ON sub.proveedorId = p.id;
```

3. El sistema muestra una lista de proveedores ordenados por el número de compras recibidas
en el último mes.

```sql
+------------------------+------------------+
| nombre                 | comprasProveedor |
+------------------------+------------------+
| Proveedores Bicis S.A. |                1 |
| Accesorios Bike Ltda.  |                1 |
+------------------------+------------------+
```

## Caso de Uso 9: Repuestos con Menor Rotación en el Inventario

Descripción: Este caso de uso describe cómo el sistema permite consultar los repuestos que han
tenido menor rotación en el inventario, es decir, los menos vendidos.
Actores:
Administrador de Inventario
Flujo Principal:

1. El administrador de inventario ingresa al sistema.
2. El administrador selecciona la opción para consultar los repuestos con menor rotación.

```sql
SELECT r.nombre, sub.cantidadVendida
FROM repuesto r
JOIN (
   SELECT dv.repuestoId, SUM(dv.cantidad) AS cantidadVendida
   FROM detalleCompra dv
   GROUP BY dv.repuestoId
) sub ON sub.repuestoId = r.id
ORDER BY sub.cantidadVendida DESC;

```

3. El sistema muestra una lista de repuestos ordenados por la cantidad vendida, de menor a
mayor.

```sql
+-------------------+-----------------+
| nombre            | cantidadVendida |
+-------------------+-----------------+
| Cinta de Manillar |             100 |
| Frenos Shimano    |              20 |
+-------------------+-----------------+
```

## Caso de Uso 10: Ciudades con Más Ventas Realizadas

Descripción: Este caso de uso describe cómo el sistema permite consultar las ciudades donde se
han realizado más ventas de bicicletas.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para consultar las ciudades con más ventas realizadas.

```sql
SELECT
    ci.nombre,
    sub.cantidadVentas
FROM
    ciudad ci
JOIN
    (SELECT
        cl.ciudadId,
        COUNT(v.id) AS cantidadVentas
     FROM
        venta v
     JOIN
        cliente cl ON v.clienteId = cl.id
     GROUP BY
        cl.ciudadId
    ) sub ON ci.id = sub.ciudadId
ORDER BY
    sub.cantidadVentas DESC;

```

3. El sistema muestra una lista de ciudades ordenadas por la cantidad de ventas realizadas.

```sql
+--------+----------------+
| nombre | cantidadVentas |
+--------+----------------+
| Bogotá |              1 |
| Madrid |              1 |
+--------+----------------+
```

# Casos de Uso con Joins

## Caso de Uso 11: Consulta de Ventas por Ciudad

Descripción: Este caso de uso describe cómo el sistema permite consultar el total de ventas
realizadas en cada ciudad.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para consultar las ventas por ciudad.

```sql
SELECT c.nombre, SUM(v.total) AS ventasTotales
FROM ciudad c
JOIN cliente cl ON c.id = cl.ciudadId
JOIN venta v ON cl.id = v.clienteId
GROUP BY c.nombre, cl.ciudadId;
```

3. El sistema muestra una lista de ciudades con el total de ventas realizadas en cada una.

```sql
+--------+---------------+
| nombre | ventasTotales |
+--------+---------------+
| Bogotá |       1800.00 |
| Madrid |        800.00 |
+--------+---------------+
```

## Caso de Uso 12: Consulta de Proveedores por País

Descripción: Este caso de uso describe cómo el sistema permite consultar los proveedores
agrupados por país.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona la opción para consultar los proveedores por país.

```sql
SELECT p.nombre AS proveedor, pa.nombre AS pais
FROM proveedor p
JOIN ciudad c ON p.ciudadId = c.id
JOIN pais pa ON c.paisId = pa.id;
```

3. El sistema muestra una lista de países con los proveedores en cada país.

```sql
+------------------------+----------+
| proveedor              | pais     |
+------------------------+----------+
| Proveedores Bicis S.A. | Colombia |
| Accesorios Bike Ltda.  | España   |
+------------------------+----------+
```

## Caso de Uso 13: Compras de Repuestos por Proveedor

Descripción: Este caso de uso describe cómo el sistema permite consultar el total de repuestos
comprados a cada proveedor.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona la opción para consultar las compras de repuestos por
proveedor.

```sql
SELECT p.nombre, SUM(dc.cantidad) AS totalComprados
FROM detalleCompra dc
JOIN compra c ON  c.id = dc.compraId
JOIN proveedor p ON p.id = c.proveedorId
GROUP BY c.proveedorId;
```

3. El sistema muestra una lista de proveedores con el total de repuestos comprados a cada
uno.

```sql
+------------------------+----------------+
| nombre                 | totalComprados |
+------------------------+----------------+
| Proveedores Bicis S.A. |             20 |
| Accesorios Bike Ltda.  |            100 |
+------------------------+----------------+
```

## Caso de Uso 14: Clientes con Ventas en un Rango de Fechas

Descripción: Este caso de uso describe cómo el sistema permite consultar los clientes que han
realizado compras dentro de un rango de fechas específico.
Actores:
Vendedor
Administrador
Flujo Principal:

1. El usuario ingresa al sistema.
2. El usuario selecciona la opción para consultar los clientes con ventas en un rango de fechas.
3. El usuario ingresa las fechas de inicio y fin del rango.

```sql
SELECT DISTINCT c.nombre
FROM  cliente c
JOIN venta v ON c.id = v.clienteId
WHERE v.fecha BETWEEN '2024-01-01' AND '2024-12-31';

```

4. El sistema muestra una lista de clientes que han realizado compras dentro del rango de
fechas especificado.

```sql
+------------+
| nombre     |
+------------+
| Juan Pérez |
| Ana Gómez  |
+------------+
```

# Casos de Uso para Implementar Procedimientos Almacenados

## Caso de Uso 1: Actualización de Inventario de Bicicletas

Descripción: Este caso de uso describe cómo el sistema actualiza el inventario de bicicletas
cuando se realiza una venta.
Actores:
Vendedor
Flujo Principal:

1. El vendedor ingresa al sistema.
2. El vendedor registra una venta de bicicletas.

```sql
CALL registrarVenta(1,@ventaId);
```

3. El sistema llama a un procedimiento almacenado para actualizar el inventario de las
bicicletas vendidas.
4. El procedimiento almacenado actualiza el stock de cada bicicleta.

```sql

DELIMITER $$
DROP PROCEDURE IF EXISTS actualizarStockBicicleta
CREATE PROCEDURE actualizarStockBicicleta(
    IN inVentaId INT
)
BEGIN
    UPDATE bicicleta b
    JOIN detalleVenta dv ON b.id = dv.bicicletaId
    SET b.stock = b.stock - dv.cantidad
    WHERE dv.ventaId = inVentaId;
END $$
DELIMITER ;

```

## Caso de Uso 2: Registro de Nueva Venta

Descripción: Este caso de uso describe cómo el sistema registra una nueva venta, incluyendo la
creación de la venta y la inserción de los detalles de la venta.
Actores:
Vendedor
Flujo Principal:

1. El vendedor ingresa al sistema.
2. El vendedor registra una nueva venta.

```sql
CALL registrarVentaConDetalles(1,1,10,@ventaId);
```

3. El sistema llama a un procedimiento almacenado para registrar la venta y sus detalles.
4. El procedimiento almacenado inserta la venta y sus detalles en las tablas correspondientes.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS registrarVentaConDetalles$$
CREATE PROCEDURE registrarVentaConDetalles(
    IN inClienteId VARCHAR(10),
    IN inBicicletaId INT,
    IN inCantidad INT,
    OUT outVentaId INT
)
BEGIN
    DECLARE precioUnitario DECIMAL(10, 2);
    DECLARE totalDetalle DECIMAL(10, 2);

    INSERT INTO venta(fecha, clienteId, total)
    VALUES (NOW(), inClienteId, 0);

    SET outVentaId = LAST_INSERT_ID();

    SELECT precio INTO precioUnitario
    FROM bicicleta
    WHERE id = inBicicletaId;

    SET totalDetalle = precioUnitario * inCantidad;

    INSERT INTO detalleVenta (ventaId, bicicletaId, cantidad, precioUnitario)
    VALUES (outVentaId, inBicicletaId, inCantidad, precioUnitario);

    UPDATE venta
    SET total = totalDetalle
    WHERE id = outVentaId;

    UPDATE bicicleta
    SET stock = stock - inCantidad
    WHERE id = inBicicletaId;

    IF (SELECT stock FROM bicicleta WHERE id = inBicicletaId) < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stock insuficiente para la venta';
    END IF;
END $$

DELIMITER ;
```

## Caso de Uso 3: Generación de Reporte de Ventas por Cliente

Descripción: Este caso de uso describe cómo el sistema genera un reporte de ventas para un
cliente específico, mostrando todas las ventas realizadas por el cliente y los detalles de cada venta.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona un cliente para generar un reporte de ventas.

```sql
CALL generarReporteVentasPorCliente(1,1);
```

3. El sistema llama a un procedimiento almacenado para generar el reporte.
4. El procedimiento almacenado obtiene las ventas y los detalles de las ventas realizadas por el
cliente.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS generarReporteVentasPorCliente$$
CREATE PROCEDURE GenerarReporteVentasPorCliente(
    IN inClienteId INT,
    IN inVentaId INT
)
BEGIN
    -- Seleccionar todas las ventas realizadas por el cliente --
    SELECT v.id AS ventaId, v.fecha, v.total
    FROM venta v
    WHERE v.clienteId = inClienteId
    ORDER BY v.fecha DESC;

    -- Seleccionar los detalles de la venta específica si se proporciona el id de venta --
    IF inVentaId IS NOT NULL THEN
       SELECT dv.bicicletaId, b.modelo, b.marca, dv.cantidad, dv.precioUnitario
        FROM detalleVenta dv
        JOIN bicicleta b ON dv.bicicletaId = b.id
        WHERE dv.ventaId = inVentaId;
    END IF;
END $$
DELIMITER ;
```

## Caso de Uso 4: Registro de Compra de Repuestos
Descripción: Este caso de uso describe cómo el sistema registra una nueva compra de repuestos
a un proveedor.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador registra una nueva compra.

```sql
CALL registrarCompra("fecha",1,10000,@compraId);
```

3. El sistema llama a un procedimiento almacenado para registrar la compra y sus detalles.
4. El procedimiento almacenado inserta la compra y sus detalles en las tablas correspondientes
y actualiza el stock de repuestos.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS registrarCompra$$
CREATE PROCEDURE registrarCompra(
    IN inFecha DATE,
    IN inProveedorId INT,
    IN inTotal DECIMAL(10, 2),
    OUT outCompraId INT
)
BEGIN
    -- Crear una nueva compra --
    INSERT INTO compra (fecha, proveedorId, total)
    VALUES (inFecha, inProveedorId, inTotal);

    -- Obtener el ID de la nueva compra creada --
    SET outCompraId = LAST_INSERT_ID();
END $$
DELIMITER ;
```

## Caso de Uso 5: Generación de Reporte de Inventario

Descripción: Este caso de uso describe cómo el sistema genera un reporte de inventario de
bicicletas y repuestos.
Actores:
Administrador de Inventario
Flujo Principal:

1. El administrador de inventario ingresa al sistema.
2. El administrador solicita un reporte de inventario.

```sql
CALL reporteInventario()
```

3. El sistema llama a un procedimiento almacenado para generar el reporte.

4. El procedimiento almacenado obtiene la información del inventario de bicicletas y repuestos.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS reporteInventario$$
CREATE PROCEDURE reporteInventario()
BEGIN
    -- Mostrar una tabla que devuelve todo el inventario de bicicleta --
    SELECT
        b.id,
        b.modelo,
        b.marca,
        b.precio,
        b.stock
    FROM bicicleta b
    ORDER BY b.id DESC;

    -- Mostrar otra tabla que devuelve todo el inventario de repuestos --
    SELECT
        r.id,
        r.nombre,
        r.descripcion,
        r.precio,
        r.stock,
        r.proveedorId AS id_proveedor
    FROM repuesto r
    ORDER BY r.id DESC;
END $$
DELIMITER ;
```

## Caso de Uso 6: Actualización Masiva de Precios

Descripción: Este caso de uso describe cómo el sistema permite actualizar masivamente los
precios de todas las bicicletas de una marca específica.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para actualizar los precios de una marca específica.
3. El administrador ingresa la marca y el porcentaje de incremento.

```sql
CALL actualizarPreciosPorMarca("marca",20);
```

4. El sistema llama a un procedimiento almacenado para actualizar los precios.
5. El procedimiento almacenado actualiza los precios de todas las bicicletas de la marca
especificada.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS actualizarPreciosPorMarca$$
CREATE PROCEDURE actualizarPreciosPorMarca(
    IN inMarca VARCHAR(255),
    IN inPorcentaje DECIMAL(5, 2)
)
BEGIN
    -- Actualizar los precios de todas las bicicletas de la marca especificada --
    UPDATE bicicleta
    SET precio = precio * (1 + inPorcentaje / 100)
    WHERE marca = inMarca;
END $$
DELIMITER ;
```

## Caso de Uso 7: Generación de Reporte de Clientes por Ciudad

Descripción: Este caso de uso describe cómo el sistema genera un reporte de clientes agrupados
por ciudad.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para generar un reporte de clientes por ciudad.

```sql
CALL reporteClienteCiudad();
```

3. El sistema llama a un procedimiento almacenado para generar el reporte.

4. El procedimiento almacenado obtiene la información de los clientes agrupados por ciudad.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS reporteClienteCiudad$$
CREATE PROCEDURE reporteClienteCiudad()
BEGIN

    SELECT
        ci.nombre AS ciudad,
        c.id AS clienteId,
        c.nombre AS cliente,
        c.correo AS correoCliente,
        c.telefono AS telefonoCliente
    FROM cliente c
    JOIN ciudad ci
    ON
        ci.id = c.ciudadId
    ORDER BY
        ci.nombre,
        c.nombre
END $$
DELIMITER ;

```

## Caso de Uso 8: Verificación de Stock antes de Venta

Descripción: Este caso de uso describe cómo el sistema verifica el stock de una bicicleta antes de
permitir la venta.
Actores:
Vendedor
Flujo Principal:

1. El vendedor ingresa al sistema.
2. El vendedor selecciona una bicicleta para vender.
3. El sistema llama a un procedimiento almacenado para verificar el stock.

```sql
CALL verificarStockBicicleta(1,20);
```

4. El procedimiento almacenado devuelve un mensaje indicando si hay suficiente stock para
realizar la venta.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS verificarStockBicicleta$$
CREATE PROCEDURE verificarStockBicicleta(
    IN inBicicletaId INT,
    IN inCantidad INT
)
BEGIN
    DECLARE stockActual INT;

    SELECT b.stock INTO stockActual
    FROM bicicleta b
    WHERE b.id = inBicicletaId;

    IF stockActual < inCantidad THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stock insuficiente para esta bicicleta';
    END IF;
END $$
DELIMITER ;

```

## Caso de Uso 9: Registro de Devoluciones

Descripción: Este caso de uso describe cómo el sistema registra la devolución de una bicicleta por
un cliente.
Actores:
Vendedor
Flujo Principal:

1. El vendedor ingresa al sistema.
2. El vendedor registra una devolución de bicicleta.

```sql
CALL registrarDevolucion("clienteId",1,1);
```

3. El sistema llama a un procedimiento almacenado para registrar la devolución.
4. El procedimiento almacenado inserta la devolución y actualiza el stock de la bicicleta.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS actualizarStockBicicleta$$
CREATE PROCEDURE actualizarStockBicicleta(
    IN inBicicletaId INT,
    IN inCantidad INT
)
BEGIN
    UPDATE bicicleta
    SET stock = stock + inCantidad
    WHERE id = inBicicletaId;
END $$

DELIMITER ;


DELIMITER $$
DROP PROCEDURE IF EXISTS registrarDevolucion$$
CREATE PROCEDURE registrarDevolucion(
    IN inClienteId INT,
    IN inBicicletaId INT,
    IN inCantidad INT
)
BEGIN
    INSERT INTO devolucion (clienteId, bicicletaId, fecha, cantidad)
    VALUES (inClienteId, inBicicletaId, CURDATE(), inCantidad);

    -- Actualizar el stock de la bicicleta
    CALL actualizarStockBicicleta(inBicicletaId, inCantidad);
END $$
DELIMITER ;
```

## Caso de Uso 10: Generación de Reporte de Compras por Proveedor
Descripción: Este caso de uso describe cómo el sistema genera un reporte de compras realizadas
a un proveedor específico, mostrando todos los detalles de las compras.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona un proveedor para generar un reporte de compras.

```sql
CALL reporteComprasPorProveedor(1);
```

3. El sistema llama a un procedimiento almacenado para generar el reporte.
4. El procedimiento almacenado obtiene las compras y los detalles de las compras realizadas al
proveedor.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS reporteComprasPorProveedor$$
CREATE PROCEDURE reporteComprasPorProveedor(
    IN inProveedorId INT
)
BEGIN

    SELECT
        c.id AS CompraID,
        c.fecha,
        c.total,
        dc.repuestoID,
        r.nombre AS RepuestoNombre,
        dc.cantidad,
        dc.precioUnitario
    FROM
        compra c
    JOIN
        detalleCompra dc ON c.id = dc.compraId
    JOIN
        Repuestos r ON dc.RepuestoID = r.ID
    WHERE
        c.proveedorId = inProveedorId
    ORDER BY
        c.fecha DESC;
END $$
DELIMITER ;
```

## Caso de Uso 11: Calculadora de Descuentos en Ventas

Descripción: Este caso de uso describe cómo el sistema aplica un descuento a una venta antes de
registrar los detalles de la venta.
Actores:
Vendedor
Flujo Principal:

1. El vendedor ingresa al sistema.
2. El vendedor aplica un descuento a una venta.
3. El sistema llama a un procedimiento almacenado para calcular el total con descuento.
4. El procedimiento almacenado calcula el total con el descuento aplicado y registra la venta.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS registrarVentaDescuento$$
CREATE PROCEDURE registrarVentaDescuento(
    IN inClienteId INT,
    IN inDescuento DECIMAL(5, 2),
    IN inBicicletaId INT,
    IN inCantidad INT,
    IN inPrecioUnitario DECIMAL(10, 2)
)
BEGIN
    DECLARE v_Total DECIMAL(10, 2);
    DECLARE v_TotalConDescuento DECIMAL(10, 2);
    DECLARE v_VentaID INT;

    -- Calcular el total de la venta
    SET v_Total = inCantidad * inPrecioUnitario;

    -- Calcular el total con el descuento aplicado
    SET v_TotalConDescuento = v_Total - (v_Total * inDescuento / 100);

    -- Insertar la venta
    INSERT INTO venta (fecha, clienteId, total)
    VALUES (NOW(), inClienteId, v_TotalConDescuento);

    -- Obtener el ID de la nueva venta creada
    SET v_VentaID = LAST_INSERT_ID();

    -- Insertar el detalle de la venta
    INSERT INTO detalleVenta (ventaId, bicicletaId, cantidad, precioUnitario)
    VALUES (v_VentaID, inBicicletaId, inCantidad, inPrecioUnitario);

    -- Actualizar el stock de la bicicleta
    UPDATE bicicleta
    SET stock = stock - inCantidad
    WHERE id = inBicicletaId;
END $$
DELIMITER ;

```

# Casos de Uso para Funciones de Resumen

## Caso de Uso 1: Calcular el Total de Ventas Mensuales

Descripción: Este caso de uso describe cómo el sistema calcula el total de ventas realizadas en un
mes específico.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el total de ventas mensuales.
3. El administrador ingresa el mes y el año.

```sql
CALL ventasPorMes(7;
```

4. El sistema llama a un procedimiento almacenado para calcular el total de ventas.
5. El procedimiento almacenado devuelve el total de ventas del mes especificado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS ventasPorMes$$
CREATE PROCEDURE ventasPorMes(
    in inMes INT
)
BEGIN
    SELECT SUM(total) AS totalVentas
    FROM venta
    WHERE MONTH(fecha) = inMes
    GROUP BY MONTH(fecha);
END$$
DELIMITER ;
```

## Caso de Uso 2: Calcular el Promedio de Ventas por Cliente

Descripción: Este caso de uso describe cómo el sistema calcula el promedio de ventas realizadas
por un cliente específico.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el promedio de ventas por cliente.
3. El administrador ingresa el ID del cliente.

```sql
CALL promedioVentasPorCliente("clienteId");
```

4. El sistema llama a un procedimiento almacenado para calcular el promedio de ventas.
5. El procedimiento almacenado devuelve el promedio de ventas del cliente especificado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS promedioVentasPorCliente$$
CREATE PROCEDURE promedioVentasPorCliente(
    IN inClienteId VARCHAR(10)
)
BEGIN
    SELECT
        c.nombre,
        TRUNCATE((AVG(v.total)),2) AS promedioVentas
    FROM
        venta v
    JOIN cliente c ON v.clienteId = c.id
    WHERE
        c.id = inClienteId
    GROUP BY
        c.id, c.nombre;
END$$
DELIMITER ;
```

## Caso de Uso 3: Contar el Número de Ventas Realizadas en un Rango de
Fechas
Descripción: Este caso de uso describe cómo el sistema cuenta el número de ventas realizadas
dentro de un rango de fechas específico.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para contar el número de ventas en un rango de
fechas.
3. El administrador ingresa las fechas de inicio y fin.

```sql
CALL ventasEnRangoFechas("fecha1","fecha2";
```

4. El sistema llama a un procedimiento almacenado para contar las ventas.
5. El procedimiento almacenado devuelve el número de ventas en el rango de fechas
especificado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS ventasEnRangoFechas $$
CREATE PROCEDURE ventasEnRangoFechas(
    IN inFechaInicio DATE,
    IN inFechaFin DATE
)
BEGIN
    SELECT COUNT(v.id) AS totalVentas
    FROM venta v
    WHERE v.fecha BETWEEN inFechaInicio AND inFechaFin;
END$$
DELIMITER ;

```

## Caso de Uso 4: Calcular el Total de Repuestos Comprados por Proveedor

Descripción: Este caso de uso describe cómo el sistema calcula el total de repuestos comprados a
un proveedor específico.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona la opción para calcular el total de repuestos comprados por
proveedor.
3. El administrador ingresa el ID del proveedor.

```sql
CALL totalRepuestosPorProveedor(1);
```

4. El sistema llama a un procedimiento almacenado para calcular el total de repuestos.
5. El procedimiento almacenado devuelve el total de repuestos comprados al proveedor
especificado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS totalRepuestosPorProveedor$$
CREATE PROCEDURE totalRepuestosPorProveedor(
    IN inProveedorID INT
)
BEGIN
    SELECT
        p.nombre,
        SUM(dc.cantidad) AS totalRepuestos
    FROM detalleCompra dc
    JOIN compra c ON dc.compraId = c.id
    JOIN proveedor p ON c.proveedorId = p.id
    WHERE p.id = inProveedorId
    GROUP BY c.proveedorId, p.nombre;
END$$
DELIMITER ;
```

## Caso de Uso 5: Calcular el Ingreso Total por Año

Descripción: Este caso de uso describe cómo el sistema calcula el ingreso total generado en un
año específico.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el ingreso total por año.
3. El administrador ingresa el año.

```sql
CALL ingresoTotalPorAño(2024);
```

4. El sistema llama a un procedimiento almacenado para calcular el ingreso total.
5. El procedimiento almacenado devuelve el ingreso total del año especificado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS ingresoTotalPorAño $$
CREATE PROCEDURE ingresoTotalPorAño(
    IN inAño INT
)
BEGIN
    SELECT
        SUM(v.total) AS ingresoTotal
    FROM venta v
    WHERE
        YEAR(v.fecha) = inAño;
END $$
DELIMITER ;
```

## Caso de Uso 6: Calcular el Número de Clientes Activos en un Mes

Descripción: Este caso de uso describe cómo el sistema cuenta el número de clientes que han
realizado al menos una compra en un mes específico.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para contar el número de clientes activos en un mes.
3. El administrador ingresa el mes y el año.

```sql
CALL clientesActivosEnMes(7,2024);
```

4. El sistema llama a un procedimiento almacenado para contar los clientes activos.
5. El procedimiento almacenado devuelve el número de clientes que han realizado compras en
el mes especificado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS clientesActivosEnMes $$
CREATE PROCEDURE clientesActivosEnMes(
    IN inMes INT,
    IN inAño INT)
BEGIN
    SELECT
        COUNT(DISTINCT v.clienteId) AS clientesActivos
    FROM venta v
    WHERE MONTH(v.fecha) = inMes AND YEAR(v.fecha) = inAño;
END$$
DELIMITER ;
```

## Caso de Uso 7: Calcular el Promedio de Compras por Proveedor

Descripción: Este caso de uso describe cómo el sistema calcula el promedio de compras
realizadas a un proveedor específico.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona la opción para calcular el promedio de compras por proveedor.
3. El administrador ingresa el ID del proveedor.

```sql
CALL promedioComprasPorProveedor(1);
```

4. El sistema llama a un procedimiento almacenado para calcular el promedio de compras.
5. El procedimiento almacenado devuelve el promedio de compras del proveedor especificado.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS promedioComprasPorProveedor $$
CREATE PROCEDURE promedioComprasPorProveedor(
    IN inProveedorId INT
)
BEGIN
    SELECT
        p.nombre,
        TRUNCATE((AVG(c.total)),2) AS promedioCompras
    FROM compra c
    JOIN proveedor p ON c.proveedorId = p.id
    WHERE p.id = inProveedorId
    GROUP BY c.proveedorId, p.nombre;
END $$
DELIMITER ;
```

## Caso de Uso 8: Calcular el Total de Ventas por Marca

Descripción: Este caso de uso describe cómo el sistema calcula el total de ventas agrupadas por
la marca de las bicicletas vendidas.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el total de ventas por marca.

```sql
CALL ventasPorMarca()
```

3. El sistema llama a un procedimiento almacenado para calcular el total de ventas por marca.
4. El procedimiento almacenado devuelve el total de ventas agrupadas por marca.

```sql

DELIMITER $$
DROP PROCEDURE IF EXISTS ventasPorMarca
CREATE PROCEDURE ventasPorMarca()
BEGIN
    SELECT
        b.marca,
        SUM(dv.cantidad * b.precioUnitario) AS total_marca
    FROM detalleVenta dv
    JOIN bicicleta b ON dv.bicicletaId = b.id
    GROUP BY b.marca;
END$$
DELIMITER ;
```

## Caso de Uso 9: Calcular el Promedio de Precios de Bicicletas por Marca

Descripción: Este caso de uso describe cómo el sistema calcula el promedio de precios de las
bicicletas agrupadas por marca.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el promedio de precios por marca.

```sql
CALL promedioPorMarca();
```

3. El sistema llama a un procedimiento almacenado para calcular el promedio de precios.
4. El procedimiento almacenado devuelve el promedio de precios agrupadas por marca.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS promedioPorMarca$$
CREATE PROCEDURE promedioPorMarca()
BEGIN
    SELECT
        b.marca,
        TRUNCATE((AVG(b.precio)),2) AS promedio
    FROM bicicleta b
    GROUP BY b.marca;
END$$
DELIMITER ;
```

## Caso de Uso 10: Contar el Número de Repuestos por Proveedor

Descripción: Este caso de uso describe cómo el sistema cuenta el número de repuestos
suministrados por cada proveedor.
Actores:
Administrador de Compras
Flujo Principal:

1. El administrador de compras ingresa al sistema.
2. El administrador selecciona la opción para contar el número de repuestos por proveedor.

```sql
CALL totalRepuestos();
```

3. El sistema llama a un procedimiento almacenado para contar los repuestos.
4. El procedimiento almacenado devuelve el número de repuestos suministrados por cada
proveedor.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS totalRepuestos$$
CREATE PROCEDURE totalRepuestos()
BEGIN
    SELECT
        p.nombre,
        SUM(dc.cantidad) AS totalRepuestos
    FROM detalleCompra dc
    JOIN compra c ON dc.compraId = c.id
    JOIN proveedor p ON c.proveedorId = p.id
    GROUP BY c.proveedorId, p.nombre;
END $$
DELIMITER ;
```

## Caso de Uso 11: Calcular el Total de Ingresos por Cliente

Descripción: Este caso de uso describe cómo el sistema calcula el total de ingresos generados por
cada cliente.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el total de ingresos por cliente.

```sql
CALL totalIngresosPorCliente();
```

3. El sistema llama a un procedimiento almacenado para calcular el total de ingresos.
4. El procedimiento almacenado devuelve el total de ingresos generados por cada cliente.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS totalIngresosPorCliente$$
CREATE PROCEDURE totalIngresosPorCliente()
BEGIN
    SELECT
        c.id AS clienteId,
        c.nombre,
        SUM(v.total) AS ingresoTotal
    FROM cliente c
    JOIN venta v ON c.id = v.clienteId
    GROUP BY c.id, c.nombre
END $$
DELIMITER ;
```

## Caso de Uso 12: Calcular el Promedio de Compras Mensuales

Descripción: Este caso de uso describe cómo el sistema calcula el promedio de compras
realizadas mensualmente por todos los clientes.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el promedio de compras mensuales.

```sql
CALL promedioComprasMensuales();
```

3. El sistema llama a un procedimiento almacenado para calcular el promedio de compras
mensuales.
4. El procedimiento almacenado devuelve el promedio de compras realizadas mensualmente.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS promedioComprasMensuales$$
CREATE PROCEDURE promedioComprasMensuales()
BEGIN
    SELECT
        YEAR(v.fecha) AS año,
        MONTH(v.fecha) AS mes,
        TRUNCATE((AVG(v.total)),2) AS promedio
    FROM venta v
    GROUP BY YEAR(v.fecha), MONTH(v.fecha);
END $$
DELIMITER ;
```

## Caso de Uso 13: Calcular el Total de Ventas por Día de la Semana

Descripción: Este caso de uso describe cómo el sistema calcula el total de ventas realizadas en
cada día de la semana.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el total de ventas por día de la semana.

```sql
CALL totalVentasPorDiaSemana(27);
```

3. El sistema llama a un procedimiento almacenado para calcular el total de ventas.
4. El procedimiento almacenado devuelve el total de ventas agrupadas por día de la semana.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS totalVentasPorDiaSemana$$
CREATE PROCEDURE totalVentasPorDiaSemana(
    IN inDia INT
)
BEGIN
    SELECT
        DAY(v.fecha) AS dia,
        SUM(v.total) AS totalVentas
    FROM venta v
    WHERE DAY(v.fecha) = inDia
    GROUP BY DAY(v.fecha);
END $$
DELIMITER ;
```

## Caso de Uso 14: Contar el Número de Ventas por Categoría de Bicicleta

Descripción: Este caso de uso describe cómo el sistema cuenta el número de ventas realizadas
para cada categoría de bicicleta (por ejemplo, montaña, carretera, híbrida).
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para contar el número de ventas por categoría de
bicicleta.

```sql
CALL ventasPorBicicleta(1);
```

3. El sistema llama a un procedimiento almacenado para contar las ventas.
4. El procedimiento almacenado devuelve el número de ventas por categoría de bicicleta.

```sql
DELIMITER $$
DROP PROCEDURE IF EXISTS ventasPorBicicleta$$
CREATE PROCEDURE ventasPorBicicleta(
    IN inBicicletaId INT
)
BEGIN
    SELECT
        dv.bicicletaId,
        SUM(dv.cantidad) AS cantidad,
        dv.precioUnitario
    FROM detalleVenta dv
    WHERE dv.bicicletaId = inBicicletaId
    GROUP BY dv.bicicletaId, dv.precioUnitario;
END$$
DELIMITER ;
```

## Caso de Uso 15: Calcular el Total de Ventas por Año y Mes

Descripción: Este caso de uso describe cómo el sistema calcula el total de ventas realizadas cada
mes, agrupadas por año.
Actores:
Administrador
Flujo Principal:

1. El administrador ingresa al sistema.
2. El administrador selecciona la opción para calcular el total de ventas por año y mes.

```sql
CALL totalVentasAñoMes(7,2024);
```

3. El sistema llama a un procedimiento almacenado para calcular el total de ventas.

```sql
DELIMITER $$
CREATE PROCEDURE totalVentasAñoMes(
    IN inMes INT,
    IN inAño INT
)
BEGIN
    SELECT
        SUM(v.total) AS totalVentas_año_mes
    FROM venta v
    WHERE (MONTH(v.fecha) = inMes) AND (YEAR(v.fecha) = inAño)
    GROUP BY MONTH(v.fecha), YEAR(v.fecha);
END$$
DELIMITER ;
```
4. El procedimiento almacenado devuelve el total de ventas agrupadas por año y mes.

```sql
+---------------------+
| totalVentas_año_mes |
+---------------------+
|             2600.00 |
+---------------------+
```

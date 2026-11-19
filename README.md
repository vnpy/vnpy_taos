# VeighNa Apache IoTDB database adapter

`vnpy_iotdb` stores VeighNa bar and tick history in Apache IoTDB using the
Tree data model and the official `apache-iotdb` Python client.

## Compatibility

- Apache IoTDB server: 2.0.x
- Python: 3.10 or later
- VeighNa: 4.x database adapter interface

Bars and ticks are represented as measurements beneath one device path for
each symbol, exchange, and (for bars) interval. Identifier components are
encoded into path-safe segments and decoded by the overview methods. The
adapter sends timestamps in milliseconds. Keep IoTDB's `timestamp_precision`
at its default `ms` value; sub-millisecond datetime precision is truncated.

## Install and configure

```bash
pip install vnpy_iotdb
```

Set these fields in VeighNa's global database settings, then restart Trader:

| Setting | Meaning | Example |
| --- | --- | --- |
| `database.name` | Provider module name | `iotdb` |
| `database.host` | IoTDB RPC host | `127.0.0.1` |
| `database.port` | IoTDB RPC port | `6667` |
| `database.database` | Tree database name, or full `root.<name>` path | `vnpy` |
| `database.user` | IoTDB username | Set for your deployment |
| `database.password` | IoTDB password | Set through local VeighNa settings |
| `database.timezone` | Session and naive datetime timezone | `Asia/Shanghai` |

Optional pool controls are `database.iotdb.pool_size` (default `5`),
`database.iotdb.wait_timeout_ms` (default `30000`), and
`database.iotdb.query_timeout_ms` (default `30000`).

## Behavior

- Writes use IoTDB `Tablet` batches of at most 1,000 rows.
- Reads filter on inclusive start and end timestamps.
- Bar and tick overview counts and time bounds are calculated from stored
  measurements, so they remain correct after repeated timestamp upserts.
- Delete methods remove all stored points for the selected device and return
  the number of points counted before deletion. IoTDB timeseries schemas remain
  available for later writes.
- Call `Database.close()` when the owning application shuts down to close the
  connection pool.

This adapter targets the Tree model only. It does not create IoTDB Table-model
tables or translate between Tree and Table data.

## Development

Run the offline adapter tests with:

```bash
python -m pytest
```

The tests mock the IoTDB session and do not require a running database.

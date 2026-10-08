# article.registry

Adapter `Protocol` + an open-closed registry keyed by platform name.

Adding a platform means writing one async adapter function and decorating it
with [`register_adapter()`](#article.registry.register_adapter) — no edits to the engine, the CLI, or any switch
statement (open-closed). Adapters are plain async callables (favour functions
over classes) that satisfy [`PublishAdapter`](#article.registry.PublishAdapter); they receive their config
and secrets by injection from the engine and never reach into globals.

### Functions

| [`available_adapters`](#article.registry.available_adapters)()   | The platform names with a registered adapter (sorted).   |
|-------------------------------------------------------------------------|----------------------------------------------------------|
| [`get_adapter`](#article.registry.get_adapter)(name)      | Resolve the adapter registered under `name`.             |
| [`is_registered`](#article.registry.is_registered)(name)    | Whether an adapter is registered under `name`.           |
| [`register_adapter`](#article.registry.register_adapter)(name) | Decorator registering an adapter callable under `name`.  |

### Classes

| [`PublishAdapter`](#article.registry.PublishAdapter)(\*args, \*\*kwargs)   | The contract every platform adapter satisfies.   |
|---------------------------------------------------------------------------------------|--------------------------------------------------|

### *class* article.registry.PublishAdapter(\*args, \*\*kwargs)

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

The contract every platform adapter satisfies.

An adapter is an `async` callable. The engine injects:

- `article`: the validated [`Article`](article.config.md#article.config.Article).
- `canonical_url`: the SSOT URL (`None` only for the primary, which
  *defines* it; secondaries must receive and honour it).
- `config`: the platform’s config model (overrides + options).
- `secrets`: the minimal credentials/identity for this platform.

and receives a [`PublishResult`](article.base.md#article.base.PublishResult) back.

### article.registry.available_adapters()

The platform names with a registered adapter (sorted).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### article.registry.get_adapter(name)

Resolve the adapter registered under `name`.

* **Return type:**
  [`PublishAdapter`](#article.registry.PublishAdapter)

```pycon
>>> get_adapter("nope")
Traceback (most recent call last):
...
article.base.UnknownPlatformError: ...no adapter registered for 'nope'...
```

### article.registry.is_registered(name)

Whether an adapter is registered under `name`.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### article.registry.register_adapter(name)

Decorator registering an adapter callable under `name`.

```pycon
>>> @register_adapter("demo")
... async def publish(article, *, canonical_url, config, secrets):
...     ...
```

# Migration Guides

This section provides guides for migrating to new features and patterns in kibana-py.

```{toctree}
:maxdepth: 2
:caption: Migration Guides

space-support
log-forwarding
```

## Available Guides

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} Space Support Migration
:link: space-support
:link-type: doc

Learn how to migrate your code to use the new space support features, including space-scoped operations and the `space_id` parameter pattern.
:::

:::{grid-item-card} Log Forwarding Migration
:link: log-forwarding
:link-type: doc

Migrate from trace-only OpenTelemetry configuration to include log forwarding for complete observability.
:::

::::

## When to Use Migration Guides

Migration guides help you:

- **Adopt new features** while maintaining backward compatibility
- **Update existing code** to use improved patterns
- **Understand breaking changes** and how to address them
- **Optimize your implementation** with best practices

## Migration Support

If you encounter issues during migration:

1. Check the {doc}`../troubleshooting/index` section
2. Review the {doc}`../user-guide/index` for detailed feature documentation
3. Consult the {doc}`../api-reference/index` for API details
4. Open an issue on [GitHub](https://github.com/pedro-angel/kibana-py) for additional help

## Version Compatibility

Each migration guide specifies:

- **Minimum version** required for new features
- **Deprecated features** and their removal timeline
- **Backward compatibility** guarantees
- **Testing recommendations** to validate your migration

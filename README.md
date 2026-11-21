# hyperopenx_notom

SlapOS software releases of Notom. Each software release has its own folder.

| Folder | Software release |
| --- | --- |
| [telegraf](telegraf/) | Telegraf with an OPC UA input and an MQTT output |

## Use a software release

The URL of a software release is the raw URL of its `software.cfg`, at a fixed
commit. For example:

```
https://raw.githubusercontent.com/notomio/hyperopenx_notom/<commit>/telegraf/software.cfg
```

Each folder holds `software.cfg`, `software.cfg.json`, the instance files, the
parameter schemas, a `test/` folder and a `README.md`.

## Add a software release

1. Create a folder at the root, for example `my-software/`.
2. Put `software.cfg` and `buildout.hash.cfg` in it. Use the raw URL of a fixed
   `slapos` commit in `extends`, as `telegraf/software.cfg` does.
3. Run `update-hash` of the `slapos` repository on `buildout.hash.cfg` after each
   change of a file that it lists.

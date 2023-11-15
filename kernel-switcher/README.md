# Ubuntu Kernel Switcher

## Summary

Ubuntu Kernel Switcher is a utility that lets you switch to a specific
kernel. Notably, post-switch, that kernel becomes the default, ensuring
it remains after system updates introduce new kernels.

## Usage

To run the tool, use invoke `switch_kernel.py` with the desired kernel
as the argument. Examples:

- `switch_kernel.py 6.5`
- `switch_kernel.py generic`
- `switch_kernel.py 6.2.0-33-generic`
- `switch_kernel.py realtime`

The matching is done by looking for the string provided as argument in the
GRUB's menuentries. AKA `argument in menuentry`. No regex matching is done.

Note that the GRUB's menuentry that will be chosen is the first one that
contains the given argument.

For instance if `realtime` is used as the argument, first grub's menuentry
that matches `realtime` will be used.

If you wish to use a precise kernel string, like
`gnulinux-5.4.0-80-generic-advanced-aca31037-7571-415c-b666-f565c524c2a6`
you are free to do so.

## Testing

There `test_in_lxd_vm.py` is a script that tests the tool inside LXD's VMs.
(So it's somewhat safe to be used).

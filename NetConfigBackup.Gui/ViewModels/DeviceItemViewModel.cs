using System.Globalization;
using CommunityToolkit.Mvvm.ComponentModel;
using NetConfigBackup.Core;

namespace NetConfigBackup.Gui.ViewModels;

public partial class DeviceItemViewModel : ObservableObject
{
    public DeviceItemViewModel(DeviceConfig model)
    {
        Model = model;
    }

    public DeviceConfig Model { get; }

    [ObservableProperty]
    private bool _isSelected;

    public string DisplayLabel
        => string.IsNullOrWhiteSpace(Model.Name)
            ? (string.IsNullOrWhiteSpace(Model.Host) ? "(nuovo device)" : Model.Host)
            : Model.Name!;

    public string? Name
    {
        get => Model.Name;
        set
        {
            if (Model.Name == value) return;
            Model.Name = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(DisplayLabel));
        }
    }

    public string Vendor
    {
        get => Model.Vendor;
        set
        {
            var v = value ?? "";
            if (Model.Vendor == v) return;
            Model.Vendor = v;
            OnPropertyChanged();
        }
    }

    public string? Type
    {
        get => Model.Type;
        set
        {
            if (Model.Type == value) return;
            Model.Type = value;
            OnPropertyChanged();
        }
    }

    public string Host
    {
        get => Model.Host;
        set
        {
            var v = value ?? "";
            if (Model.Host == v) return;
            Model.Host = v;
            OnPropertyChanged();
            OnPropertyChanged(nameof(DisplayLabel));
        }
    }

    public string Port
    {
        get => Model.Port?.ToString(CultureInfo.InvariantCulture) ?? "";
        set
        {
            var trimmed = (value ?? "").Trim();
            if (string.IsNullOrWhiteSpace(trimmed))
            {
                if (Model.Port is null) return;
                Model.Port = null;
                OnPropertyChanged();
                return;
            }

            if (int.TryParse(trimmed, NumberStyles.Integer, CultureInfo.InvariantCulture, out var p) && p is > 0 and <= 65535)
            {
                if (Model.Port == p) return;
                Model.Port = p;
                OnPropertyChanged();
            }
        }
    }

    public string? Username
    {
        get => Model.Username;
        set
        {
            if (Model.Username == value) return;
            Model.Username = value;
            OnPropertyChanged();
        }
    }

    public string? Password
    {
        get => Model.Password;
        set
        {
            if (Model.Password == value) return;
            Model.Password = value;
            OnPropertyChanged();
        }
    }
}

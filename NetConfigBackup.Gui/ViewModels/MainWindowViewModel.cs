using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using NetConfigBackup.Core;

namespace NetConfigBackup.Gui.ViewModels;

public partial class MainWindowViewModel : ViewModelBase
{
    private BackupConfigFile _config = new();

    public MainWindowViewModel()
    {
        ConfigPath = "devices.json";
        Devices = new ObservableCollection<DeviceItemViewModel>();

        LoadCommand = new AsyncRelayCommand(LoadAsync);
        SaveCommand = new AsyncRelayCommand(SaveAsync);
        AddCommand = new RelayCommand(AddDevice);
        DeleteCommand = new RelayCommand(DeleteSelected, () => SelectedDevice is not null);
        SelectAllCommand = new RelayCommand(() => SetSelection(true));
        SelectNoneCommand = new RelayCommand(() => SetSelection(false));

        StatusMessage = "Pronto.";
    }

    public string[] Vendors { get; } = ["cisco", "fortigate", "mikrotik", "paloalto", "ssh"];
    public string[] Types { get; } = ["auto", "ssh", "fortigate-api", "paloalto-api"]; 

    [ObservableProperty]
    private string _configPath = "devices.json";

    [ObservableProperty]
    private string _statusMessage = "";

    public ObservableCollection<DeviceItemViewModel> Devices { get; }

    private DeviceItemViewModel? _selectedDevice;
    public DeviceItemViewModel? SelectedDevice
    {
        get => _selectedDevice;
        set
        {
            SetProperty(ref _selectedDevice, value);
            DeleteCommand.NotifyCanExecuteChanged();
        }
    }

    public IAsyncRelayCommand LoadCommand { get; }
    public IAsyncRelayCommand SaveCommand { get; }
    public IRelayCommand AddCommand { get; }
    public RelayCommand DeleteCommand { get; }
    public IRelayCommand SelectAllCommand { get; }
    public IRelayCommand SelectNoneCommand { get; }

    private async Task LoadAsync()
    {
        try
        {
            if (!File.Exists(ConfigPath))
            {
                _config = new BackupConfigFile();
                Devices.Clear();
                SelectedDevice = null;
                StatusMessage = $"File non trovato: {ConfigPath} (creato vuoto in memoria)";
                return;
            }

            _config = await BackupConfigIo.LoadAsync(ConfigPath);
            Devices.Clear();

            foreach (var d in _config.Devices)
                Devices.Add(new DeviceItemViewModel(d));

            SelectedDevice = Devices.FirstOrDefault();
            StatusMessage = $"Caricati {Devices.Count} device da {ConfigPath}";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Errore load: {ex.Message}";
        }
    }

    private async Task SaveAsync()
    {
        try
        {
            _config.Devices = Devices.Select(d => d.Model).ToList();
            await BackupConfigIo.SaveAsync(ConfigPath, _config);
            StatusMessage = $"Salvato: {ConfigPath}";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Errore save: {ex.Message}";
        }
    }

    private void AddDevice()
    {
        var model = new DeviceConfig
        {
            Vendor = "ssh",
            Type = "ssh",
            Host = "",
        };

        var vm = new DeviceItemViewModel(model);
        Devices.Add(vm);
        SelectedDevice = vm;
        StatusMessage = "Aggiunto nuovo device.";
    }

    private void DeleteSelected()
    {
        if (SelectedDevice is null)
            return;

        var idx = Devices.IndexOf(SelectedDevice);
        Devices.Remove(SelectedDevice);

        if (Devices.Count == 0)
        {
            SelectedDevice = null;
        }
        else
        {
            if (idx >= Devices.Count) idx = Devices.Count - 1;
            SelectedDevice = Devices[idx];
        }

        StatusMessage = "Device eliminato.";
    }

    private void SetSelection(bool selected)
    {
        foreach (var d in Devices)
            d.IsSelected = selected;

        StatusMessage = selected ? "Selezionati tutti." : "Deselezionati tutti.";
    }
}

using System.Windows;
using System.Windows.Controls;
using Microsoft.Web.WebView2.Core;

namespace JANIS.Desktop.Views;

public partial class WebPanelView : UserControl
{
    string _pendingUrl = "";

    public WebPanelView()
    {
        InitializeComponent();
        Loaded += OnLoaded;
    }

    public async void Navigate(string url)
    {
        _pendingUrl = url;
        if (Browser.CoreWebView2 != null)
            Browser.CoreWebView2.Navigate(url);
    }

    async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            await Browser.EnsureCoreWebView2Async();
            if (!string.IsNullOrEmpty(_pendingUrl))
                Browser.CoreWebView2.Navigate(_pendingUrl);
        }
        catch (Exception ex)
        {
            StatusText.Text = "WebView2: " + ex.Message;
        }
    }
}

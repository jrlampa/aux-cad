namespace OxCad.Integration
{
    /// <summary>
    /// Catálogo de capacidades funcionais que um provedor de integração pode suportar.
    /// Define operações de domínio sem acoplamento a implementações ou fornecedores específicos.
    /// </summary>
    public enum IntegrationCapability
    {
        // Documentos e Arquivos
        DocumentRead,
        DocumentWrite,
        ArtifactRead,
        ArtifactWrite,

        // Ordens de Serviço e Processos
        WorkOrderRead,
        WorkOrderWrite,

        // Sistemas de Negócio e ERP
        BusinessDataRead,
        BusinessDataWrite,

        // Clientes e CRM
        CustomerRead,
        CustomerWrite,

        // Identidade e Usuários
        IdentityRead,
        UserRead,

        // Mensageria e Eventos
        EventSubscribe,
        EventPublish,

        // Protocolos Genéricos
        RestCall,
        SoapCall
    }
}
